# Contributing

## Development setup

```bash
git clone https://github.com/derekgallardo01/outlook-copilot-sorter
cd outlook-copilot-sorter
pip install -e ".[graph,webhook,llm]"
```

## Running tests

```bash
python -m pytest -q
```

## Running golden classification evals

```bash
python evals/run.py
```

## Adding a new label class

1. Add a `LabelConfig` entry to `DEFAULT_CATALOG` in
   `src/outlook_copilot_sorter/classifier.py`
2. Add the routing tuple to `ROUTING` in the same file
3. If the class should get a drafted reply, add a template to
   `DEFAULT_TEMPLATES` in `copilot_drafter.py`
4. Add fixture emails in `backend.py::DEFAULT_INBOX` that exercise it
5. Add golden test cases in `evals/golden.json`
6. Add pytest cases in `tests/test_classifier.py`

## Pull-request checklist

- [ ] All tests pass locally (`python -m pytest -q`)
- [ ] All evals pass locally (`python evals/run.py`)
- [ ] CHANGELOG.md updated
