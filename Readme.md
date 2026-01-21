# 📘 Repository Management & Contribution Guidelines

This document defines how contributors interact with the repository, how code is validated, and how we maintain a secure and high-quality codebase.  
It applies to all developers working on this project.

---

# 1. 🔐 Permissions & Security Model

To ensure code integrity and prevent accidental production issues:

### Repository Permissions
- **Maintainers (Edgar, Youssef):**  
  Full write access. Can merge pull requests, manage settings, and maintain CI/CD.
- **Contributors / Interns:**  
  **No write access** to the main repository. Must contribute through forks and pull requests (PRs).

This guarantees that:
- No one can accidentally push to the `main` branch  
- Every change is reviewed  
- CI validates code before merging  

---

# 2. 🔀 Contribution Workflow (Mandatory)

All contributions must follow this workflow.

## Step 1 — Fork the repository
Each developer creates their own **private fork** of the main repository.

> GitHub automatically keeps forks of private repositories private.  
> Contributors must not change the visibility of their fork.

---

## Step 2 — Create a feature branch
Always create a dedicated branch for each feature or fix:

```bash
git checkout -b feature/my-change
```

Do **not** commit directly on `main`.

---

## Step 3 — Develop and commit code
Commit changes normally and push them to your fork:

```bash
git push origin feature/my-change
```

---

## Step 4 — Open a Pull Request
From GitHub → *New Pull Request* → compare your fork & branch to the main repository.

Opening a PR triggers:

- Automated tests  
- Linting/formatting checks  
- Manual review by a maintainer  

A PR can be merged **only when all checks pass** and at least one maintainer approves.

---

# 3. 🧪 Automated Quality Gates

The CI pipeline enforces several rules before merging code.

### Each PR must pass:
- Unit tests (when enabled by the team)
- A valid `README.md` must exist
- A `main.py` file must exist (for Python components)
- Running `python main.py` must exit with `0`
- All CI checks must pass successfully

These ensure that the project stays consistent and production-ready.

---

# 4. 🛠 Branch Protection Rules

The `main` branch is protected:

- ❌ No direct pushes  
- ✔ Pull request required  
- ✔ All checks must pass  
- ✔ At least 1 reviewer approval  
- ✔ No force pushes  
- ✔ Branch cannot be deleted accidentally  

This guarantees stability and safety.

---

# 5. 🔔 PR Notifications

A Discord webhook notifies the team when:

- A PR is created  
- A PR is updated  
- A PR is merged  

This accelerates review speed and makes collaboration smoother.

---

# 6. 📝 Developer Responsibilities

Contributors must:

- Keep their fork synced using:
  ```bash
  git fetch upstream
  git merge upstream/main
  ```
- Work exclusively in feature branches  
- Follow coding and formatting guidelines  
- Write clear commit messages  
- Ensure CI tests pass locally before opening a PR  
- Keep their fork **private**  

---

# 7. 👨‍🏫 Intern Onboarding Summary

Interns should learn:

- Why direct pushes are disabled  
- The fork → branch → PR workflow  
- CI ensures production safety  
- Maintain high code quality  
- Ask questions early  

---

# 8. ✅ Benefits of This Workflow

- Strong protection against regressions  
- Clear review process  
- Predictable deployments  
- Higher code quality  
- Scales with team growth  

---

# 9. 📬 Questions

If you need help with your first PR, contact a maintainer.
