//! rewind-ingest: statement ingestion abstractions (CSV/PDF text) and bank-specific parsers.

pub mod types;
pub mod parsers;

pub use types::{StatementTransaction, StatementKind};
