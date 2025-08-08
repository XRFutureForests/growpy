***

> When generating or explaining Python code, always: use explicit top-of-file imports, keep code primarily atomic functions (classes only if needed), allow external packages, fail fast, format with Black, output only when essential, use tqdm only for time-consuming loops, include meaningful docstrings/comments for future test automation, and always consult the docs/ folder for relevant context.

***

#### Detailed Guidance

**Imports**  
- Always use explicit imports (e.g., from tqdm import tqdm).  
- All imports must be at the very top of the file.

**Code Structure**  
- Prefer functions over top-level scripts or classes.  
- Use classes only if necessary; otherwise, default to small, reusable functions.  
- Keep functions atomic—each should perform exactly one task.

**Formatting**  
- Format code as if passed through Black (PEP8, 88-character lines).  
- Prioritize brevity while keeping readability.

**Error Handling**  
- No try/except unless it’s unavoidable.  
- Fail fast—let exceptions propagate if they indicate real issues.  
- Minimal sanity checks allowed for critical steps.

**Progress Bars**  
- Use tqdm only for operations that take noticeable time.  
- Avoid adding them to trivial loops.

**Dependencies**  
- External packages are welcome; use them when they improve clarity or reduce code length.  
- Avoid heavyweight libraries unless justified.

**Output**  
- Default to silent execution.  
- Only print when essential to task output or workflow.

**Documentation**  
- Use docstrings in functions/classes with parameters, return values, and purpose clearly stated.  
- Keep inline comments only where they add value.  
- Write documentation to enable automated test generation later.

**Response Formatting**  
- Always output the final Python script first, then a short explanation if needed.  
- Do not create extra files unless explicitly required; if created temporarily for testing, delete them in the same code block.  
- Always check the docs/ folder for relevant project context before coding.
