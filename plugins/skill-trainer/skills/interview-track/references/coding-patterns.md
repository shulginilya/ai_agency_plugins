# Coding patterns

Each pattern has the **signal** in the problem that should trigger it and the
**shape** of the solution. The ids match `trainer.py topics --area coding`.

## Patterns

| id | Signal in the problem | Shape | Usual complexity |
| --- | --- | --- | --- |
| two-pointers | sorted array, pairs/triplets, palindrome, in-place partition | `l=0, r=n-1`, move the side that cannot improve | O(n) |
| sliding-window | longest/shortest contiguous subarray or substring with a constraint | grow `r`, shrink `l` while invalid, track the best | O(n) |
| hashing-prefix-sums | counts, "seen before", subarray sum equals k | map of value→count or prefix→count | O(n) |
| binary-search | sorted input, or "minimum X such that feasible(X)" | `lo, hi`, `while lo < hi`, keep the invariant explicit | O(log n) or O(n log M) |
| stacks-monotonic | next greater/smaller, matching brackets, histogram | stack of indices, pop while the invariant breaks | O(n) |
| linked-lists | in-place reorder, cycle, middle, merge | dummy head, fast/slow pointers, reverse a half | O(n) |
| trees-traversal | anything on a tree | recursive DFS returning a value up; BFS with a queue for levels | O(n) |
| heaps-top-k | k largest/smallest/most frequent, running median, merge k | heap of size k; two heaps for the median | O(n log k) |
| intervals | overlaps, merging, rooms needed | sort by start; sweep; a min-heap of end times | O(n log n) |
| graphs-bfs-dfs | grid, islands, shortest path in steps, weighted paths | BFS for unweighted shortest, DFS for components, Dijkstra for weights | O(V+E), O(E log V) |
| topological-sort | dependencies, ordering, "can all be finished" | Kahn: in-degrees + queue; a cycle if not all are emitted | O(V+E) |
| union-find | connectivity merged incrementally, components, redundant edge | parent array, path compression, union by size | ~O(α(n)) per op |
| backtracking | all subsets/permutations/combinations, constraint search | choose → recurse → un-choose; prune early | exponential, say so |
| dp-1d | best/count over a sequence where each step depends on earlier ones | define `dp[i]`, the recurrence, the base case, then the order | O(n) to O(n²) |
| dp-2d-strings | two strings, a grid, edit/LCS/paths | `dp[i][j]` over prefixes; roll to one row when asked about space | O(n·m) |
| greedy | a local choice that is provably safe (exchange argument) | sort by the right key, then one pass | O(n log n) |
| tries | prefixes, many words against one board, autocomplete | node with children map and an end flag | O(total chars) |
| design-data-structure | "implement a class with these O(1) operations" | combine structures: map + doubly linked list for LRU | as specified |
| async-utilities | debounce, throttle, concurrency limit, retry | closures and timers; a queue of pending promises | — |

## The order of a drill

1. Restate the problem and the input bounds.
2. Ask about edge cases: empty input, duplicates, negatives, huge n.
3. Brute force out loud with its complexity. Then the better idea.
4. Code it. Name variables for what they hold.
5. Walk through one small example by hand, then run the tests.
6. Complexity, and what changes if n is 100× larger.

## Language notes

The language comes from `config set interview-language`. Use the section that
matches it. For a language not listed, use its standard test runner and say so.

### Node (JavaScript)

Harness, in `solution.test.js`, run with `node --test`:

```js
const { test } = require("node:test");
const assert = require("node:assert/strict");

function solve(nums, k) { /* ... */ }

test("examples", () => {
  assert.deepEqual(solve([1, 2, 3], 3), [0, 2]);
  assert.deepEqual(solve([], 1), []);
});
```

Gotchas worth saying out loud in an interview:

- **Sorting.** `arr.sort()` sorts as strings: write `arr.sort((a, b) => a - b)`.
- **No built-in heap.** Write a small binary heap (about 25 lines) or say you
  would use a library. Practise writing it once from memory.
- **Map vs object.** `Map` keeps insertion order and allows any key; objects
  turn keys into strings. Use `new Map()` for counting.
- **2D arrays.** `new Array(n).fill([])` shares one inner array. Write
  `Array.from({ length: n }, () => [])`.
- **Integer division.** `Math.floor(a / b)`, or `Math.trunc` for negatives.
  Numbers are exact only up to `2**53 - 1`; above that use `BigInt`.
- **Strings are immutable.** Build an array and `join("")`, rather than
  concatenating in a loop.
- **Recursion depth.** It is around 10k frames; for deep trees or graphs,
  iterate with an explicit stack.
- **Queues.** `shift()` is O(n). For BFS, use an index pointer into an array.

### TypeScript

Same as Node. Run with `npx tsx --test solution.test.ts`, or with
`node --test` on Node 22+ using `--experimental-strip-types`. Type the
signature first: it settles the clarifying questions.

### Python

Harness: plain `assert` lines under `if __name__ == "__main__":`, or pytest.

- `heapq` is a min-heap: push `-x` for a max-heap.
- Useful built-ins: `collections.Counter`, `defaultdict`, `deque`, and
  `bisect`.
- `[[0] * m for _ in range(n)]`, never `[[0] * m] * n`.
- `sys.setrecursionlimit` or iterate for deep recursion.
- `@functools.cache` for memoized DP: say what it costs in memory.
