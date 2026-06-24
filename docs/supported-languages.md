# Supported Languages

Breakdown uses tree-sitter for AST-aware code parsing. Languages with a
tree-sitter grammar get accurate, function-level chunking. Other languages
fall back to 50-line plain-text chunks, which still produce useful explanations.

## AST-Aware (tree-sitter)

Python, JavaScript, TypeScript, TSX, Go, Rust, Java, C, C++, Ruby, C#,
PHP, Swift, Kotlin, Scala, Lua, Bash

## Plain-Text Fallback

All other file types are chunked as plain text. This includes most config
files, markup languages, and languages not yet in tree-sitter-languages.

## Adding a Language

1. Check if the language is in `tree-sitter-languages`:
   https://github.com/grantjenks/py-tree-sitter-languages
2. If yes, add the file extension mapping to `_EXT_TO_LANGUAGE` in
   `core/src/breakdown/indexer/registry.py`.
3. If no, open a PR to `tree-sitter-languages` first, or open an issue
   here requesting it.
4. Update this file with the new language.
