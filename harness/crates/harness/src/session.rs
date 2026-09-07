use serde_json::{Value, json};

use crate::clock::utc_now_iso;
use crate::error::HarnessError;
use crate::provider::{Provider, Request, StopReason};
use crate::tool::ToolSet;
use crate::transcript::{Exchange, SessionOutcome, ToolResultRecord, Transcript, Usage};

/// Sessions are distinguished by a counter rather than by address: a session
/// can move in memory, and a provider's per-conversation state must not follow
/// it to a different conversation that happens to reuse the address.
fn next_session_id() -> u64 {
    use std::sync::atomic::{AtomicU64, Ordering};
    static NEXT: AtomicU64 = AtomicU64::new(1);
    NEXT.fetch_add(1, Ordering::Relaxed)
}

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
    /// Every exchange this session has produced, across all of its stages.
    ///
    /// A phase that formalizes twenty units used to be twenty sessions, which
    /// meant twenty cold conversations re-sending the same instructions and
    /// the same tool schemas. Keeping them here lets one conversation carry all
    /// twenty, so a provider that can resume has something to resume into.
    /// Phases still get their own session: the boundary between reading the
    /// specification and extracting from the evidence bundle is a soundness
    /// property, not a cost.
    exchanges: Vec<Exchange>,
    /// The current stage's task, until the exchange that carries it exists.
    pending_prompt: Option<String>,
    /// Whether a finished stage's turns leave the conversation.
    ///
    /// Stages that share instructions but not subject matter — one task after
    /// another — would otherwise make every stage carry all its predecessors,
    /// so the tenth task pays for the first nine. Dropping them keeps the
    /// request the size of one task while the instructions, which are what a
    /// prefix cache can actually reuse, stay byte-identical in front of it.
    ///
    /// It is only safe when a stage's prompt is self-contained: anything the
    /// stage needs from an earlier one has to be in its prompt, not in the
    /// conversation it is about to lose.
    isolated_stages: bool,
    /// Distinguishes this conversation from the others running in this process.
    id: u64,
}

impl<'a> Session<'a> {
    pub fn new(provider: &'a dyn Provider, system: impl Into<String>) -> Self {
        Self {
            provider,
            system: system.into(),
            prompt: String::new(),
            max_steps: 100,
            exchanges: Vec::new(),
            pending_prompt: None,
            isolated_stages: false,
            id: next_session_id(),
        }
    }

    pub fn with_max_steps(mut self, max_steps: u32) -> Self {
        self.max_steps = max_steps;
        self
    }

    /// Drop each stage's turns once it ends, so the conversation does not grow
    /// with the number of stages. Requires self-contained stage prompts.
    pub fn with_isolated_stages(mut self, isolated: bool) -> Self {
        self.isolated_stages = isolated;
        self
    }

    /// Drive the loop until the tool set reports completion, the model stops,
    /// or the step ceiling is reached. The transcript is returned in every
    /// case, including failure — a session that ran out of steps is exactly the
    /// one whose transcript you need to read.
    pub fn stage(
        &mut self,
        prompt: impl Into<String>,
        tools: &mut dyn ToolSet,
    ) -> (Result<(), HarnessError>, Transcript) {
        self.prompt = prompt.into();
        // The task is announced to the model once, attached to the first
        // exchange this stage produces.
        self.pending_prompt = Some(self.prompt.clone());
        let provider = self.provider;
        let started_at = utc_now_iso();
        let specs = tools.specs();
        // Earlier stages stay in the conversation but not in this stage's
        // transcript: the artifact for one unit must not contain another's.
        let stage_start = self.exchanges.len();
        let mut totals = Usage::default();
        let mut steps = 0u32;

        let outcome = loop {
            if steps >= self.max_steps {
                break Err(HarnessError::StepLimit {
                    steps: self.max_steps,
                });
            }
            steps += 1;

            let response = {
                let request = Request {
                    system: &self.system,
                    prompt: &self.prompt,
                    prompt_pending: self.pending_prompt.is_some(),
                    exchanges: &self.exchanges,
                    tools: &specs,
                    session: self.id,
                };
                match provider.turn(&request) {
                    Ok(response) => response,
                    Err(error) => break Err(error),
                }
            };
            totals.accumulate(&response.usage);

            if response.tool_calls.is_empty() {
                // The model ended its turn. Record it before deciding: a turn
                // that explains why it stopped is exactly the one worth reading.
                self.exchanges.push(Exchange {
                    prompt: self.pending_prompt.take(),
                    assistant: response.assistant,
                    tool_results: Vec::new(),
                    usage: response.usage,
                });
                // Completion is decided by the tool set, never by parsing what
                // the model said.
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
                // A turn may carry several tool calls. Once the tool set has
                // produced its artifact, running the rest would overwrite it —
                // but every tool_use still needs a tool_result, so say so.
                let (output, is_error) = if tools.finished() {
                    (
                        "not executed: this session already produced its artifact".to_string(),
                        true,
                    )
                } else {
                    let result = tools.call(&call.name, &call.input);
                    let mut output = result.to_text();
                    // The deterministic step runs for this call, and its output
                    // is attached to this call.
                    if let Some(extra) = tools.after_tool_call() {
                        output.push('\n');
                        output.push_str(&extra);
                    }
                    (output, result.is_error())
                };
                records.push(ToolResultRecord {
                    call_id: call.id.clone(),
                    name: call.name.clone(),
                    input: call.input.clone(),
                    output,
                    is_error,
                });
            }

            self.exchanges.push(Exchange {
                prompt: self.pending_prompt.take(),
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
            provider: provider.id().to_string(),
            model: provider.model().to_string(),
            started_at,
            finished_at: utc_now_iso(),
            system: self.system.clone(),
            prompt: self.prompt.clone(),
            tools: specs.iter().map(|spec| spec.name.clone()).collect(),
            max_steps: self.max_steps,
            steps,
            exchanges: self.exchanges[stage_start..].to_vec(),
            usage: totals,
            outcome: session_outcome,
        };
        if self.isolated_stages {
            // The transcript above already owns this stage's turns, so the
            // artifact keeps them even though the conversation does not.
            self.exchanges.truncate(stage_start);
        }
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
            vec![ToolSpec::new(
                "submit",
                "submit the artifact",
                json!({"type": "object"}),
            )]
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

        fn after_tool_call(&mut self) -> Option<String> {
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
        let mut tools = Fussy {
            attempts: 0,
            done: false,
            checked: 0,
        };
        let mut session = Session::new(&provider, "system");
        let (outcome, transcript) = session.stage("prompt", &mut tools);

        assert!(
            outcome.is_ok(),
            "{:?}",
            outcome.err().map(|e| e.to_string())
        );
        assert_eq!(transcript.steps, 2);
        assert_eq!(transcript.exchanges.len(), 2);
        assert!(transcript.exchanges[0].tool_results[0].is_error);
        assert!(!transcript.exchanges[1].tool_results[0].is_error);
        assert_eq!(transcript.outcome, SessionOutcome::Submitted);
        // Usage accumulates across turns, including cache reads.
        assert_eq!(transcript.usage.input_tokens, 20);
        assert_eq!(transcript.usage.cache_read_input_tokens, 14);
        // The deterministic step ran after each batch and reached the model.
        assert!(
            transcript.exchanges[0].tool_results[0]
                .output
                .contains("deterministic check #1")
        );
    }

    #[test]
    fn step_ceiling_is_enforced_and_still_yields_a_transcript() {
        let provider = RecordedProvider::new("test", vec![turn("a"), turn("b"), turn("c")]);
        let mut tools = Fussy {
            attempts: 0,
            done: false,
            checked: 0,
        };
        let mut session = Session::new(&provider, "system").with_max_steps(1);
        let (outcome, transcript) = session.stage("prompt", &mut tools);

        assert!(matches!(outcome, Err(HarnessError::StepLimit { steps: 1 })));
        assert_eq!(transcript.outcome, SessionOutcome::StepLimit);
        assert_eq!(transcript.exchanges.len(), 1);
    }

    /// Two submissions in one turn must each get their own deterministic
    /// result. Attaching one build to the wrong call would report the verdict
    /// on submission A as though it were the verdict on B.
    #[test]
    fn parallel_tool_calls_each_get_their_own_deterministic_result() {
        let both = TurnResponse {
            assistant: json!([
                {"type": "tool_use", "id": "a", "name": "submit", "input": {}},
                {"type": "tool_use", "id": "b", "name": "submit", "input": {}},
            ]),
            text: String::new(),
            tool_calls: vec![
                ToolCall {
                    id: "a".into(),
                    name: "submit".into(),
                    input: json!({}),
                },
                ToolCall {
                    id: "b".into(),
                    name: "submit".into(),
                    input: json!({}),
                },
            ],
            stop_reason: StopReason::ToolUse,
            usage: Usage::default(),
            model: "test".into(),
        };
        let provider = RecordedProvider::new("test", vec![both]);
        let mut tools = Fussy {
            attempts: 0,
            done: false,
            checked: 0,
        };
        let (outcome, transcript) = Session::new(&provider, "system").stage("prompt", &mut tools);

        assert!(
            outcome.is_ok(),
            "{:?}",
            outcome.err().map(|e| e.to_string())
        );
        let results = &transcript.exchanges[0].tool_results;
        assert_eq!(results.len(), 2, "every tool_use needs a tool_result");
        // The first is rejected and carries its own check; the second succeeds
        // and carries its own. Neither borrows the other's verdict.
        assert!(results[0].is_error);
        assert!(results[0].output.contains("NOT_YET"));
        assert!(results[0].output.contains("deterministic check #1"));
        assert!(!results[1].is_error);
        assert!(results[1].output.contains("deterministic check #2"));
    }

    /// Once the artifact exists, later calls in the same turn must not run —
    /// but must still be answered, or the next request is malformed.
    #[test]
    fn calls_after_completion_are_answered_without_being_executed() {
        let turn = |ids: &[&str]| TurnResponse {
            assistant: json!(
                ids.iter()
                    .map(|id| json!({"type": "tool_use", "id": id, "name": "submit", "input": {}}))
                    .collect::<Vec<_>>()
            ),
            text: String::new(),
            tool_calls: ids
                .iter()
                .map(|id| ToolCall {
                    id: (*id).to_string(),
                    name: "submit".into(),
                    input: json!({}),
                })
                .collect(),
            stop_reason: StopReason::ToolUse,
            usage: Usage::default(),
            model: "test".into(),
        };
        // First turn fails once; second turn submits twice.
        let provider = RecordedProvider::new("test", vec![turn(&["a"]), turn(&["b", "c"])]);
        let mut tools = Fussy {
            attempts: 0,
            done: false,
            checked: 0,
        };
        let (outcome, transcript) = Session::new(&provider, "system").stage("prompt", &mut tools);

        assert!(outcome.is_ok());
        let second = &transcript.exchanges[1].tool_results;
        assert_eq!(second.len(), 2);
        assert!(!second[0].is_error, "the first submission of the turn runs");
        assert!(second[1].is_error);
        assert!(second[1].output.contains("already produced its artifact"));
        // The tool set was called twice in total, not three times.
        assert_eq!(tools.attempts, 2);
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
        let mut tools = Fussy {
            attempts: 0,
            done: false,
            checked: 0,
        };
        let (outcome, transcript) = Session::new(&provider, "system").stage("prompt", &mut tools);

        assert!(matches!(outcome, Err(HarnessError::Incomplete { .. })));
        assert_eq!(
            transcript.outcome,
            SessionOutcome::Stopped {
                stop_reason: "end_turn".into()
            }
        );
        // The turn that explains the refusal must survive in the transcript:
        // it is the only record of why the session ended.
        assert_eq!(transcript.exchanges.len(), 1);
        assert!(transcript.exchanges[0].tool_results.is_empty());
        assert_eq!(
            transcript.exchanges[0].assistant[0]["text"],
            json!("I think that's everything.")
        );
    }

    /// The reason `Session` outlives one unit: a phase that formalizes many
    /// units is one conversation, so the second unit's request carries the
    /// first unit's exchanges and a provider that can resume has something to
    /// resume into. The per-unit transcript must still contain only that unit,
    /// because it is written next to that unit's artifact.
    #[test]
    fn a_second_stage_continues_the_conversation_but_not_the_transcript() {
        let provider =
            RecordedProvider::new("test", vec![turn("a"), turn("b"), turn("c"), turn("d")]);

        let mut session = Session::new(&provider, "system");
        let mut first = Fussy {
            attempts: 0,
            done: false,
            checked: 0,
        };
        let (outcome, first_transcript) = session.stage("unit A", &mut first);
        assert!(outcome.is_ok(), "{outcome:?}");

        let mut second = Fussy {
            attempts: 0,
            done: false,
            checked: 0,
        };
        let (outcome, second_transcript) = session.stage("unit B", &mut second);
        assert!(outcome.is_ok(), "{outcome:?}");

        // Each unit's artifact gets its own turns and nobody else's.
        assert_eq!(first_transcript.exchanges.len(), 2);
        assert_eq!(second_transcript.exchanges.len(), 2);
        assert_eq!(first_transcript.prompt, "unit A");
        assert_eq!(second_transcript.prompt, "unit B");
        // But the conversation kept growing underneath them, which is what the
        // provider sees and what makes resuming possible.
        assert_eq!(session.exchanges.len(), 4);
    }

    /// The pipeline interleaves sessions — a unit's evidence, that unit's
    /// semantics, then the next unit's evidence — through one shared provider.
    /// A provider holding per-conversation state keys it by this identity, so
    /// it must never be reused between two live sessions.
    #[test]
    fn every_session_is_distinguishable_from_the_others_in_this_process() {
        let provider = RecordedProvider::new("test", vec![turn("a")]);
        let first = Session::new(&provider, "system");
        let second = Session::new(&provider, "system");
        assert_ne!(
            first.id, second.id,
            "two sessions sharing an id would share a provider's thread"
        );
    }

    /// Ten tasks must not make the tenth carry the first nine. What a prefix
    /// cache can reuse is the instructions, which do not move; what it cannot
    /// is nine unrelated tasks in front of the request.
    #[test]
    fn an_isolated_stage_leaves_the_conversation_but_keeps_its_transcript() {
        let provider =
            RecordedProvider::new("test", vec![turn("a"), turn("b"), turn("c"), turn("d")]);
        let mut session = Session::new(&provider, "system").with_isolated_stages(true);

        let mut first = Fussy {
            attempts: 0,
            done: false,
            checked: 0,
        };
        let (outcome, first_transcript) = session.stage("task A", &mut first);
        assert!(outcome.is_ok(), "{outcome:?}");
        assert_eq!(
            first_transcript.exchanges.len(),
            2,
            "the artifact keeps the turns"
        );
        assert!(session.exchanges.is_empty(), "the conversation does not");

        let mut second = Fussy {
            attempts: 0,
            done: false,
            checked: 0,
        };
        let (outcome, second_transcript) = session.stage("task B", &mut second);
        assert!(outcome.is_ok(), "{outcome:?}");
        assert_eq!(second_transcript.exchanges.len(), 2);
        assert_eq!(second_transcript.prompt, "task B");
        // Task B was never told about task A, which is why its prompt has to
        // carry anything it needs from it.
        assert!(session.exchanges.is_empty());
    }
}
