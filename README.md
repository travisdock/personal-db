# Personal Database Assistant

A simple LLM-powered app for tracking anything: energy, journals, finances, habits, goals, books, workouts—anything you want.

## How it works

1. Talk to the assistant in natural language
2. It creates database tables based on what you want to track
3. Log entries by just describing them ("my energy was 7/10 today because...")
4. Ask for insights, summaries, patterns across all your data

## Local development

```bash
# Install dependencies
pip install -r requirements.txt

# Set your OpenAI API key
export OPENAI_API_KEY=sk-...

# Run the app
python personal_db_assistant.py
```

Open http://localhost:7860 in your browser.

## Deploy to Railway (recommended)

1. Push this code to a GitHub repo
2. Create a new project on [Railway](https://railway.app)
3. Connect your GitHub repo
4. Add environment variable: `OPENAI_API_KEY`
5. Add a volume mount for persistent data:
   - Source: `data`  
   - Destination: `/app/data`
6. Update `DB_PATH` in the code to `/app/data/personal.db`
7. Deploy!

Your app will be available at `https://your-app.up.railway.app`

## Deploy to Render

1. Push to GitHub
2. Create a new Web Service on [Render](https://render.com)
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `python personal_db_assistant.py`
5. Add environment variable: `OPENAI_API_KEY`
6. Add a disk for persistence (mount at `/data`, update `DB_PATH`)
7. Deploy!

## Voice input

Just use your phone's built-in dictation—tap the microphone icon on your keyboard while in the chat interface. Works great!

## Cost estimate

- **Hosting**: ~$5/month on Railway or free tier on Render
- **API**: ~$0.01-0.05 per conversation (gpt-4o-mini is very cheap)
- For a personal tracker used daily: expect $5-10/month total
