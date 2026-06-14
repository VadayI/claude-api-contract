// commitlint config — Conventional Commits with a Ukrainian-friendly relaxation.
//
// The TYPE prefix stays English (feat, fix, chore, docs, ...) — it is a token
// (git-operations.md). The subject text and body may be Ukrainian, so the
// case/length rules that would reject Cyrillic prose are turned off.
export default {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'subject-case': [0], // allow Ukrainian / any case in the subject text
    'body-max-line-length': [0], // allow long Ukrainian prose in the body
    'footer-max-line-length': [0],
  },
};
