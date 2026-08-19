<small>_This project was created with minimal help from AI assistants, mainly for the tests and a couple helper functions. This document is 100% human written._</small>

# `Codelexity`

![version](https://img.shields.io/pypi/v/codelexity)
![coverage](https://img.shields.io/badge/coverage-70%25-green)
![python](https://img.shields.io/badge/python-3.11%2B-blue)

A python package that helps you measure, visualize and ultimately manage code complexity.

## Motivation

In the age of AI, codebases are becoming messier and more difficult to maintain. `Codelexity` helps you visualize and manage this complexity.

## Quick Start

- Step 1: `uv add codelexity`
- Step 2: `uv run codelexity <your_package_path> --plot` - this will create a `codelexity.html` that you can open and play with in your browser.

![Codelexity Graph](https://raw.githubusercontent.com/nickgiki/codelexity/main/assets/codelexity_codelexity.png)
_Codelexity HTML report on the `codelexity` repo_


## Intuition

There's a ton of literature describing the relationship between complexity and maintainability of code.

### The basics

[Halstead measures](https://en.wikipedia.org/wiki/Halstead_complexity_measures) are pretty robust in measuring the complexity. All Halstead metrics are derived from 4 numbers:

1. $n_1$ = the number of distinct operators
2. $n_1$ = the number of distinct operands
3. $N_2$  = the total number of operators
4. $N_2$ = the total number of operands

From these, another 7 metrics can be calculated, with most important the **volume**: 

$$V=N*log_2(n)$$

where: 
- $n = n_1 + n_2$ the vocabulary of the program and 
- $N = N_1 + N_2$ the length of the program

Another important metric is the [Mc Cabe Cyclomatic Complexity](https://en.wikipedia.org/wiki/Cyclomatic_complexity) measured as:

$$M=E-N+2P$$

where $M$ the complexity, $E$ and $N$ the number of edges and nodes in the computation graph and $P$ the number of connected components.

With Halstead's volume and McCabe's complexity one can compute the [**Maintainability Index**](https://ieeexplore.ieee.org/document/242525) computed as:

$$ 171 - 5.2 * log_2(V) - 0.23 * M- 16.2 * log_2(SLOC)+ 50 * \sqrt{2.4 * perCOM}$$

where $SLOC$ the total lines of code and $perCOM$ the % of comments in the code.

Research is divided about how to interpret the score, with most academic sources (i.e. [Ardito et al., 2020](https://onlinelibrary.wiley.com/doi/10.1155/2020/8840389), [Heričko & Šumak, 2023](https://www.mdpi.com/2076-3417/13/5/2972)) citing $MI>=85$ as high, $85>MI>=65$ as medium and $MI<65$ as low and [Microsoft Visual Studio](https://learn.microsoft.com/en-us/visualstudio/code-quality/code-metrics-maintainability-index-range-and-meaning) citing $MI>=20$ as high, $20>MI>=10$ as medium and $MI<10$ as low.

This is how the metrics in this repo are calculated.

### Maintainability propagation in the package graph

It is easy to understand that a densly connected dependency graph affects the maintainability. Central nodes (those that are imported from other modules that are reachable downstream) are more likely to cause issues. Therefore central modules that are not easy to maintain affect the maintainability of the whole package.

To measure centrality, `codelexity` uses [Katz centrality](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.centrality.katz_centrality.html). The centrality value is then multiplied by the module length and normalized by the sum of the respective value in all modules. The corresponding value is used as a weight to compute the total Maintainability Index.

### Example - NetworkX

This is a result for the [`networkx` library](https://networkx.org/en/), a large and complex repo. The command used to create the analysis was:

```bash
codelexity networkx --json --plot
```

![Codelexity on NetworkX](https://raw.githubusercontent.com/nickgiki/codelexity/main/assets/codelexity_networkx.png)

Note that the flags `json` and `plot` denote whether the output will be stored as a json named `codelexity.json` and as an html `codelexity.html` in the working directory.

The `codelexity.json` containts aggregate analytics for the whole package and per-module details.

```json
{
    "analytics": {
        "total_lines": 234629,
        "total_functions": 9555,
        "total_modules": 624
    },
    "modules": {
        "conftest.py": {
            "imports": [
                "<stdlib>/importlib/metadata/__init__.py",
                "<stdlib>/os.py",
                "<stdlib>/warnings.py",
                "__init__.py"
            ],
            "total_lines": 262,
            "empty_lines": 39,
            "comments": 12,
            "code_length": 211,
...
        }
```

## Running the tests

The suite lives in `tests/` and uses the standard library's `unittest` — no test dependencies to install.

```sh
uv run python -m unittest discover        # all tests
uv run python -m unittest discover -v     # verbose, one line per test
```

Coverage, which needs no dev dependency either:

```sh
uv run --with coverage coverage run --source=src -m unittest discover
uv run --with coverage coverage report
```
