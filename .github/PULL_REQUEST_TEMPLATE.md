## What and why

<!-- One paragraph: the problem, and how this change solves it. Link the issue. -->

## How it was verified

- [ ] `make lint typecheck test`
- [ ] `make test-integration` (if API, database, cache, storage or runtime code changed)
- [ ] `make e2e qa` (if a user flow or the web app changed)
- [ ] `make tf-validate` (if Terraform changed)

## Checklist

- [ ] Docs updated (README, `docs/`, configuration reference) for any behaviour or config change
- [ ] New migration instead of editing an applied one
- [ ] OpenAPI reference regenerated (`make openapi`) when routes or schemas changed
- [ ] No secrets, account ids or real hostnames (`make sanitize` is clean)
- [ ] Security-relevant change? Described the threat and the mitigation above
