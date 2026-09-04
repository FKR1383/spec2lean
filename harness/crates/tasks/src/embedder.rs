//! Embedding a query, by keeping one Python process alive.
//!
//! The vectors in the index were written by Python, because that is where the
//! index is built and where the model lives. A search needs the query in the
//! same space, so the same code embeds it — but loading the model costs far
//! more than any single embedding, so the process is started once and asked
//! many times rather than started per search.
//!
//! An embedder that will not start is not an error. It means this run has no
//! semantic search, and lexical search still answers.

use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::mpsc::{Receiver, RecvTimeoutError, channel};
use std::time::Duration;

use serde_json::Value;

/// How long to wait for the model to load, and then for one vector.
const READY_TIMEOUT: Duration = Duration::from_secs(300);
const QUERY_TIMEOUT: Duration = Duration::from_secs(60);

pub struct Embedder {
    child: Child,
    stdin: ChildStdin,
    incoming: Receiver<String>,
    pub model: String,
}

impl Embedder {
    /// Start the server, or explain why there is no semantic search.
    pub fn start(python: &str, model: &str, source_root: &str) -> Result<Self, String> {
        let mut child = Command::new(python)
            .arg("-m")
            .arg("spec2lean.embeddings")
            .arg("--serve")
            .arg("--model")
            .arg(model)
            .env("PYTHONPATH", source_root)
            // The model is cached; a run must not become a download.
            .env("HF_HUB_OFFLINE", "1")
            .env("TRANSFORMERS_OFFLINE", "1")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|error| format!("could not start `{python} -m spec2lean.embeddings`: {error}"))?;

        let stdin = child.stdin.take().ok_or("embedder stdin was not piped")?;
        let stdout = child.stdout.take().ok_or("embedder stdout was not piped")?;
        let (sender, incoming) = channel();
        std::thread::spawn(move || {
            for line in BufReader::new(stdout).lines().map_while(Result::ok) {
                if sender.send(line).is_err() {
                    return;
                }
            }
        });

        let mut embedder = Self {
            child,
            stdin,
            incoming,
            model: model.to_string(),
        };
        // The first line is the readiness handshake, and waiting for it here is
        // what keeps a model load out of the first search's latency budget.
        match embedder.read(READY_TIMEOUT) {
            Ok(value) if value["ready"] == true => Ok(embedder),
            Ok(value) => Err(format!("the embedder did not report ready: {value}")),
            Err(error) => Err(error),
        }
    }

    fn read(&mut self, timeout: Duration) -> Result<Value, String> {
        match self.incoming.recv_timeout(timeout) {
            Ok(line) => serde_json::from_str(&line)
                .map_err(|error| format!("the embedder answered with non-JSON: {error}")),
            Err(RecvTimeoutError::Timeout) => {
                Err(format!("the embedder did not answer within {timeout:?}"))
            }
            Err(RecvTimeoutError::Disconnected) => Err("the embedder exited".into()),
        }
    }

    pub fn embed(&mut self, query: &str) -> Result<Vec<f32>, String> {
        // A newline is the record separator, so a query may not contain one.
        let flattened = query.replace('\n', " ");
        writeln!(self.stdin, "{flattened}")
            .and_then(|()| self.stdin.flush())
            .map_err(|error| format!("could not send a query to the embedder: {error}"))?;
        let value = self.read(QUERY_TIMEOUT)?;
        let vector: Vec<f32> = value["vector"]
            .as_array()
            .ok_or("the embedder answered without a vector")?
            .iter()
            .filter_map(Value::as_f64)
            .map(|value| value as f32)
            .collect();
        if vector.is_empty() {
            return Err("the embedder answered with an empty vector".into());
        }
        Ok(vector)
    }
}

impl Drop for Embedder {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

/// Merge two rankings by reciprocal rank, best first.
///
/// Lexical and semantic search fail differently: one misses a paraphrase, the
/// other drifts to something merely topical. Fusing by rank rather than by
/// score avoids comparing a similarity with a full-text relevance, which are
/// not the same quantity and not on the same scale.
pub fn fuse(lexical: &[String], semantic: &[String], limit: usize) -> Vec<String> {
    // The constant damps the first few ranks so one list cannot dominate purely
    // by being confident; 60 is the value the original description uses.
    const DAMPING: f32 = 60.0;
    let mut scored: std::collections::BTreeMap<String, f32> = std::collections::BTreeMap::new();
    for ranking in [lexical, semantic] {
        for (index, id) in ranking.iter().enumerate() {
            *scored.entry(id.clone()).or_insert(0.0) += 1.0 / (DAMPING + index as f32 + 1.0);
        }
    }
    let mut ordered: Vec<(String, f32)> = scored.into_iter().collect();
    ordered.sort_by(|left, right| {
        right
            .1
            .partial_cmp(&left.1)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| left.0.cmp(&right.0))
    });
    ordered.into_iter().take(limit).map(|(id, _)| id).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fusion_prefers_what_both_rankings_found() {
        // `b` is second in each list and first in neither, and still wins:
        // agreement is worth more than one list's confidence.
        let lexical = vec!["a".to_string(), "b".to_string()];
        let semantic = vec!["c".to_string(), "b".to_string()];
        assert_eq!(fuse(&lexical, &semantic, 3)[0], "b");
    }

    #[test]
    fn fusion_keeps_what_only_one_ranking_found() {
        // A paraphrase the lexical index cannot reach is the whole reason for
        // the second ranking, so it must not be dropped for being unmatched.
        let lexical = vec!["a".to_string()];
        let semantic = vec!["z".to_string()];
        let fused = fuse(&lexical, &semantic, 5);
        assert!(fused.contains(&"a".to_string()) && fused.contains(&"z".to_string()));
    }

    #[test]
    fn fusion_is_stable_when_scores_tie() {
        let one = vec!["b".to_string(), "a".to_string()];
        let two = vec!["a".to_string(), "b".to_string()];
        assert_eq!(fuse(&one, &two, 2), fuse(&one, &two, 2));
    }

    #[test]
    fn an_empty_ranking_contributes_nothing_and_breaks_nothing() {
        let lexical = vec!["a".to_string(), "b".to_string()];
        assert_eq!(fuse(&lexical, &[], 2), vec!["a".to_string(), "b".to_string()]);
        assert!(fuse(&[], &[], 5).is_empty());
    }

    #[test]
    fn a_missing_embedder_is_reported_rather_than_panicking() {
        match Embedder::start("python-does-not-exist", "m", "src") {
            Err(error) => assert!(error.contains("python-does-not-exist")),
            Ok(_) => panic!("an embedder that cannot start must say so"),
        }
    }
}
