use std::cell::RefCell;

use serde_json::Value;

use super::{Provider, Request, TurnResponse};
use crate::error::HarnessError;

/// A provider that replays scripted turns. Lets the whole loop — tool
/// dispatch, validation, resubmission after diagnostics, completion detection —
/// be tested without a network or an API key, which the subprocess design this
/// replaces could only do by faking `subprocess.run`.
pub struct RecordedProvider {
    turns: RefCell<std::vec::IntoIter<TurnResponse>>,
    model: String,
    pub requests: RefCell<Vec<Value>>,
}

impl RecordedProvider {
    pub fn new(model: impl Into<String>, turns: Vec<TurnResponse>) -> Self {
        Self {
            turns: RefCell::new(turns.into_iter()),
            model: model.into(),
            requests: RefCell::new(Vec::new()),
        }
    }
}

impl Provider for RecordedProvider {
    fn id(&self) -> &'static str {
        "recorded"
    }

    fn model(&self) -> &str {
        &self.model
    }

    fn turn(&self, request: &Request<'_>) -> Result<TurnResponse, HarnessError> {
        self.requests.borrow_mut().push(serde_json::json!({
            "system": request.system,
            "prompt": request.prompt,
            "exchanges": request.exchanges.len(),
            "tools": request.tools.iter().map(|spec| spec.name.clone()).collect::<Vec<_>>(),
        }));
        self.turns
            .borrow_mut()
            .next()
            .ok_or_else(|| HarnessError::Transport("recorded provider ran out of turns".into()))
    }
}
