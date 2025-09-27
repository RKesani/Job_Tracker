from mlx_lm import load, generate

model, tokenizer = load("mlx-community/gemma-3-270m-it-8bit")

# System prompt for job posting extraction
system_prompt = """Extract the following fields from the job posting text below. 
Return JSON only, no extra text.

Fields:
- company
- title
- location
- url
- salary_range

Job Posting:
<insert scraped job text here>"""

prompt = """Forward Deployed Software Engineer
Candid Health · Menlo Park, CA · Onsite · Full-time · Mid-level

Salary: $135,000 - $205,000 / year

Job Description
We're building the infrastructure that makes healthcare easy to pay for and easy to get paid for. As a Forward Deployed Software Engineer, you'll be embedded with our customers to design, build, and ship solutions that streamline revenue cycle operations. You'll work directly with providers, payers, and partners to understand requirements and translate them into scalable code.

Responsibilities
- Design and implement new product features
- Fix bugs and improve performance
- Collaborate with teammates across product and engineering
- Work closely with customers to gather feedback and iterate
- Communicate effectively with technical and non-technical stakeholders

Requirements
- Strong software engineering background
- 3+ years experience building and shipping software
- Proficiency in modern programming languages (e.g., Python, TypeScript, or similar)
- Experience designing technical solutions end-to-end
- Ability to thrive in ambiguous, fast-paced environments
- Excellent communication skills
- Comfort working directly with customers

Compensation and Benefits
- Salary range: $135,000 - $205,000
- Health, dental, vision insurance
- Flexible PTO
- 401(k) with company match

Apply at: https://jobs.ashbyhq.com/candidhealth/71365073-41fb-40a8-b23a-3e02306770a5
"""

# Combine system prompt with job posting
full_prompt = system_prompt.replace("<insert scraped job text here>", prompt)

if tokenizer.chat_template is not None:
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
    full_prompt = tokenizer.apply_chat_template(
        messages, add_generation_prompt=True
    )

response = generate(model, tokenizer, prompt=full_prompt, verbose=True)