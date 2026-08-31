use serde_json::{Value, json};

use crate::clock::utc_now_iso;
use crate::error::HarnessError;
use crate::provider::{Provider, Request, StopReason};
use crate::tool::ToolSet;
use crate::transcript::{Exchange, SessionOutcome, ToolResultRecord, Transcript, Usage};

/// One bounded agent session.
///
/// This is the whole replacement for `opencode run --pure` plus its synthesized
/// config, its five `OPENCODE_*` escape hatches, its disabled-tool table, its
/// permission table, its stdio MCP server, and its stdout scraping. The tool
/// set runs in this process, so a tool call is a function call.
pub struct Session<'a> {
    provider: &'a dyn Provider,
    system: String,
    prompt: String,
    max_steps: u32,
}

impl<'a> Session<'a> {
    pub fn new(
        provider: &'a dyn Provider,
        system: impl Into<String>,
        prompt: impl Into<String>,
    ) -> Self {
        Self {
            provider,
            system: system.into(),
            prompt: prompt.into(),
            max_steps: 100,
        }
    }

    pub fn with_max_steps(mut self, max_steps: u32) -> Self {
        self.max_steps = max_steps;
        self
    }

    /// Drive the loop until the tool set reports completion, the model stops,
    /// or the step ceiling is reached. The transcript is returned in every
    /// case, including failure — a session that ran out of steps is exactly the
    /// one whose transcript you need to read.
    pub fn run(&self, tools: &mut dyn ToolSet) -> (Result<(), HarnessError>, Transcript) {
        let started_at = utc_now_iso();
        let specs = tools.specs();
        let mut exchanges: Vec<Exchange> = Vec::new();
        let mut totals = Usage::default();
        let mut steps = 0u32;

        let outcome = loop {
            if steps >= self.max_steps {
                break Err(HarnessError::StepLimit {
                    steps: self.max_steps,
                });
            }
            steps += 1;

            let request = Request {
                system: &self.system,
                prompt: &self.prompt,
                exchanges: &exchanges,
                tools: &specs,
            };
            let response = match self.provider.turn(&request) {
                Ok(response) => response,
                Err(error) => break Err(error),
            };
            totals.accumulate(&response.usage);

            if response.tool_calls.is_empty() {
                // The model ended its turn. Completion is decided by the tool
                // set, never by parsing what the model said.
                break if tools.finished() {
                    Ok(())
                } else {
                    Err(HarnessError::Incomplete {
                        stop_reason: response.stop_reason.as_str().to_string(),
                        steps,
                    })
                };
            }

            let mut records = Vec::with_capacity(response.tool_calls.len());
            for call in &response.tool_calls {
                let result = tools.call(&call.name, &call.input);
                records.push(ToolResultRecord {
                    call_id: call.id.clone(),
                    name: call.name.clone(),
                    input: call.input.clone(),
                    output: result.to_text(),
                    is_error: result.is_error(),
                });
            }

            // The harness's own deterministic step: run a compiler or a checker
            // and hand the model its output in this same conversation.
            if let Some(extra) = tools.after_tools()
                && let Some(last) = records.last_mut()
            {
                last.output.push('\n');
                last.output.push_str(&extra);
            }

            exchanges.push(Exchange {
                assistant: response.assistant,
                tool_results: records,
                usage: response.usage,
            });

            if tools.finished() {
                break Ok(());
            }
            if response.stop_reason != StopReason::ToolUse
                && response.stop_reason != StopReason::EndTurn
            {
                break Err(HarnessError::Incomplete {
                    stop_reason: response.stop_reason.as_str().to_string(),
                    steps,
                });
            }
        };

        let session_outcome = match &outcome {
            Ok(()) => SessionOutcome::Submitted,
            Err(HarnessError::StepLimit { .. }) => SessionOutcome::StepLimit,
            Err(HarnessError::Incomplete { stop_reason, .. }) => SessionOutcome::Stopped {
                stop_reason: stop_reason.clone(),
            },
            Err(error) => SessionOutcome::Stopped {
                stop_reason: error.to_string(),
            },
        };

        let transcript = Transcript {
            schema_version: 1,
            provider: self.provider.id().to_string(),
            model: self.provider.model().to_string(),
            started_at,
            finished_at: utc_now_iso(),
            system: self.system.clone(),
            prompt: self.prompt.clone(),
            tools: specs.iter().map(|spec| spec.name.clone()).collect(),
            max_steps: self.max_steps,
            steps,
            exchanges,
            usage: totals,
            outcome: session_outcome,
        };
        (outcome, transcript)
    }
}

/// Convenience for adapters and tests: an assistant turn that calls one tool.
pub fn anthropic_tool_use(id: &str, name: &str, input: Value) -> Value {
    json!([{ "type": "tool_use", "id": id, "name": name, "input": input }])
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::provider::recorded::RecordedProvider;
    use crate::provider::{StopReason, ToolCall, TurnResponse};
    use crate::tool::{ToolOutcome, ToolSpec};

    /// A tool set that accepts only the second submission, so the test covers
    /// the diagnostic-and-resubmit path the deterministic validators rely on.
    struct Fussy {
        attempts: u32,
        done: bool,
        checked: u32,
    }

    impl ToolSet for Fussy {
        fn specs(&self) -> Vec<ToolSpec> {
            vec![ToolSpec::new("submit", "submit the artifact", json!({"type": "object"}))]
        }

        fn call(&mut self, name: &str, _input: &Value) -> ToolOutcome {
            if name != "submit" {
                return ToolOutcome::Err(format!("unknown tool: {name}"));
            }
            self.attempts += 1;
            if self.attempts < 2 {
                return ToolOutcome::Err("NOT_YET: try once more".into());
            }
            self.done = true;
            ToolOutcome::Ok(json!({"accepted": true}))
        }

        fn finished(&self) -> bool {
            self.done
        }

        fn after_tools(&mut self) -> Option<String> {
            self.checked += 1;
            Some(format!("deterministic check #{}", self.checked))
        }
    }

    fn turn(id: &str) -> TurnResponse {
        TurnResponse {
            assistant: anthropic_tool_use(id, "submit", json!({})),
            text: String::new(),
            tool_calls: vec![ToolCall {
                id: id.to_string(),
                name: "submit".into(),
                input: json!({}),
            }],
            stop_reason: StopReason::ToolUse,
            usage: Usage {
                input_tokens: 10,
                output_tokens: 5,
                cache_creation_input_tokens: 0,
                cache_read_input_tokens: 7,
            },
            model: "test".into(),
        }
    }

    #[test]
    fn resubmits_after_a_diagnostic_then_completes() {
        let provider = RecordedProvider::new("test", vec![turn("a"), turn("b")]);
        let mut tools = Fussy { attempts: 0, done: false, checked: 0 };
        let session = Session::new(&provider, "system", "prompt");
        let (outcome, transcript) = session.run(&mut tools);

        assert!(outcome.is_ok(), "{:?}", outcome.err().map(|e| e.to_string()));
        assert_eq!(transcript.steps, 2);
        assert_eq!(transcript.exchanges.len(), 2);
        assert!(transcript.exchanges[0].tool_results[0].is_error);
        assert!(!transcript.exchanges[1].tool_results[0].is_error);
        assert_eq!(transcript.outcome, SessionOutcome::Submitted);
        // Usage accumulates across turns, including cache reads.
        assert_eq!(transcript.usage.input_tokens, 20);
        assert_eq!(transcript.usage.cache_read_input_tokens, 14);
        // The deterministic step ran after each batch and reached the model.
        assert!(transcript.exchanges[0].tool_results[0].output.contains("deterministic check #1"));
    }

    #[test]
    fn step_ceiling_is_enforced_and_still_yields_a_transcript() {
        let provider = RecordedProvider::new("test", vec![turn("a"), turn("b"), turn("c")]);
        let mut tools = Fussy { attempts: 0, done: false, checked: 0 };
        let session = Session::new(&provider, "system", "prompt").with_max_steps(1);
        let (outcome, transcript) = session.run(&mut tools);

        assert!(matches!(outcome, Err(HarnessError::StepLimit { steps: 1 })));
        assert_eq!(transcript.outcome, SessionOutcome::StepLimit);
        assert_eq!(transcript.exchanges.len(), 1);
    }

    #[test]
    fn a_model_that_stops_without_submitting_is_a_failure() {
        let stop = TurnResponse {
            assistant: json!([{"type": "text", "text": "I think that's everything."}]),
            text: "I think that's everything.".into(),
            tool_calls: vec![],
            stop_reason: StopReason::EndTurn,
            usage: Usage::default(),
            model: "test".into(),
        };
        let provider = RecordedProvider::new("test", vec![stop]);
        let mut tools = Fussy { attempts: 0, done: false, checked: 0 };
        let (outcome, transcript) = Session::new(&provider, "system", "prompt").run(&mut tools);

        assert!(matches!(outcome, Err(HarnessError::Incomplete { .. })));
        assert_eq!(
            transcript.outcome,
            SessionOutcome::Stopped { stop_reason: "end_turn".into() }
        );
    }
}
