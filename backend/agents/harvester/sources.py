"""Target company list for the Harvester agent.

All companies are categorized by their career page API type:
  - GREENHOUSE_SOURCES: companies using the Greenhouse ATS (JSON API available)
  - LEVER_SOURCES: companies using the Lever ATS (JSON API available)
  - HTML_SOURCES: companies with raw HTML career pages (BeautifulSoup parsing)
"""

# Greenhouse Jobs Board API: https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs
GREENHOUSE_SOURCES = [
    {"company": "Anthropic", "board_token": "anthropic"},
    {"company": "OpenAI", "board_token": "openai"},
    {"company": "Cohere", "board_token": "cohere"},
    {"company": "Scale AI", "board_token": "scaleai"},
    {"company": "Hugging Face", "board_token": "huggingface"},
    {"company": "Weights & Biases", "board_token": "wandb"},
    {"company": "Runway", "board_token": "runwayml"},
    {"company": "Perplexity", "board_token": "perplexity"},
    {"company": "Mistral AI", "board_token": "mistral"},
    {"company": "Character.AI", "board_token": "character"},
    {"company": "Stability AI", "board_token": "stability"},
    {"company": "Midjourney", "board_token": "midjourney"},
    {"company": "Together AI", "board_token": "togetherai"},
    {"company": "Groq", "board_token": "groq"},
]

# Lever Postings API: https://api.lever.co/v0/postings/{handle}?mode=json
LEVER_SOURCES = [
    {"company": "Notion", "handle": "notion"},
    {"company": "Linear", "handle": "linear"},
    {"company": "Figma", "handle": "figma"},
    {"company": "Vercel", "handle": "vercel"},
    {"company": "Replit", "handle": "replit"},
    {"company": "Cursor", "handle": "anysphere"},
    {"company": "Luma AI", "handle": "luma-ai"},
]

# Raw HTML sources (BeautifulSoup parsing)
# url: the canonical careers listing page
HTML_SOURCES = [
    {
        "company": "Google DeepMind",
        "url": "https://deepmind.google/careers/",
        "job_selector": "a[href*='/careers/']",
    },
    {
        "company": "Meta AI",
        "url": "https://www.metacareers.com/jobs/?offices[0]=Menlo%20Park%2C%20CA&teams[0]=Artificial%20Intelligence%20(AI)%20Research",
        "job_selector": "a[href*='/jobs/']",
    },
    {
        "company": "Microsoft Research",
        "url": "https://jobs.careers.microsoft.com/global/en/search?q=research+AI&lc=United%20States",
        "job_selector": "a[href*='/job/']",
    },
]

# All sources combined, keyed by type — for convenience imports
ALL_SOURCES = {
    "greenhouse": GREENHOUSE_SOURCES,
    "lever": LEVER_SOURCES,
    "html": HTML_SOURCES,
}
