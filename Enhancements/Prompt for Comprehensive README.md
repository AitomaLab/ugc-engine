# Prompt for Google Antigravity: Generate a Comprehensive README.md

---

## Copy everything below this line and paste it into Antigravity

---

Analyze the entire codebase of this project and generate a comprehensive, professional `README.md` file. The README must give any developer everything they need to clone this repo and run it locally without asking me a single question.

Follow these instructions:

### 1. Auto-Detect the Tech Stack

Scan all config files, lock files, and source code to identify:

- Programming languages and their versions (e.g., TypeScript 5.x, Python 3.11)
- Frameworks and libraries (e.g., Next.js 14, React, TailwindCSS, Flask, Express)
- Databases and ORMs (e.g., PostgreSQL + Prisma, MongoDB + Mongoose, Supabase, Drizzle)
- Runtimes and their required versions (e.g., Node.js >= 18, Python >= 3.10)
- Package managers (e.g., npm, pnpm, yarn, pip, poetry)
- Any other services or tools the project depends on (e.g., Redis, Docker, Stripe CLI)

### 2. Generate the README.md with These Sections

**Project Title and Description**
- A clear project title
- A 2–3 sentence description of what the project does and its purpose

**Tech Stack**
- A clean list or table of all detected technologies, grouped by category (Frontend, Backend, Database, DevOps, etc.)

**Prerequisites**
- Everything that must be installed on the local machine BEFORE cloning
- Include exact version requirements where detectable
- Include links to official download/install pages
- Examples: Node.js, Python, Docker, specific CLIs, database engines, etc.

**Getting Started**

Step-by-step, copy-pasteable terminal commands covering:

1. Clone the repo
2. Navigate into the project directory
3. Install all dependencies (using the correct package manager detected)
4. Set up environment variables:
   - If `.env` files exist, create a `.env.example` with all keys listed but values redacted
   - Instruct the user to copy `.env.example` to `.env` and fill in their own values
   - Briefly describe what each variable is for
5. Database setup (if applicable):
   - Migrations, seeding, or any initial DB commands needed
6. Start the development server
   - Include the exact command and the expected local URL (e.g., `http://localhost:3000`)

**Available Scripts / Commands**
- List all useful scripts from `package.json`, `Makefile`, `pyproject.toml`, or equivalent
- Include what each script does (e.g., `npm run build` — creates a production build)

**Project Structure**
- A brief directory tree or explanation of the main folders and what they contain
- Focus on the top 1–2 levels, not every file

**Environment Variables Reference**
- A table listing every environment variable the project uses:
  - Variable name
  - Description
  - Required or optional
  - Example value (redacted if sensitive)

**Deployment Notes** (if applicable)
- If deployment configs exist (Vercel, Netlify, Docker, Railway, etc.), briefly describe the deployment setup
- Note any differences between local dev and production

**Troubleshooting / Common Issues** (if applicable)
- Any known gotchas, common setup errors, or platform-specific notes

**Contributing**
- A short section encouraging contributions
- Link to `CONTRIBUTING.md` if it exists

**License**
- Reference the license file if one exists

### 3. Formatting Rules

- Use GitHub-flavored Markdown
- Use fenced code blocks with language hints for all terminal commands and code
- Use tables where they improve clarity (e.g., env vars, scripts)
- Use clear heading hierarchy (h2 for sections, h3 for subsections)
- Keep it scannable — a developer should find what they need in under 10 seconds

### 4. Also Do This

- If a `.env.example` file does not already exist, create one alongside the README
- If the project has multiple services or packages (monorepo), document setup for each
- If there are any post-install steps (e.g., `npx prisma generate`, `python manage.py migrate`), include them in the correct order

Do not skip any section. Do not assume the reader knows anything about this project. Write it so someone cloning this repo cold can be up and running in minutes.
