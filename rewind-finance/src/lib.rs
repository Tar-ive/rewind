//! rewind-finance: AMEX CSV parser, category rules, quota tracker, and task emitter

pub mod amex_parser;
pub mod category_rules;
pub mod task_emitter;

pub use amex_parser::{AmexTransaction, parse_amex_csv};
pub use category_rules::categorize;
pub use task_emitter::TaskEmitter;
