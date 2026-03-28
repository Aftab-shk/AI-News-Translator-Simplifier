# AI News Simplifier and Translator

This project provides a comprehensive solution for making complex news articles more accessible by summarizing them into concise, factual statements and translating them into various regional languages.

The system is composed of three main parts:
- A FastAPI backend powered by Google Vertex AI (Gemini) and Google Cloud Translation.
- A user-friendly web interface for processing full text directly from the browser.
- A Chrome extension to allow on-the-fly simplification and translation of selected text while browsing.

## Features

- **AI Summarization**: Condenses long, complex articles into 3-5 factual sentences. The summaries are strictly limited to the main events and outcomes, omitting unnecessary dramatic language or interpretations.
- **Multi-Language Support**: Translates text accurately from its source language into a wide range of regional languages, including Bengali, Gujarati, Hindi, Kannada, Marathi, Punjabi, Tamil, Telugu, Urdu, Malayalam, Odia, Assamese, and Sanskrit.
- **Browser Extension**: A Chrome extension that lets you highlight web content and receive simplified translations without leaving the page.
- **Evaluation Engine**: Automatically evaluates the similarity of the summary and the consistency of the translation against the original text using an integrated evaluation system.

## Project Structure

- **Backend**: Contains the FastAPI application (`main.py`) which manages API requests, talks to Google Cloud services for summarization and translation, and evaluates the generated content.
- **Frontend**: Contains the Chrome Extension source code, including the manifest file, background scripts, and popup interfaces.
- **Website**: Contains the HTML, CSS, and JS files for the standalone web application.

## Prerequisites

- Python 3.8+
- Google Cloud Platform account with Vertex AI and Translation APIs enabled.
- A Google Cloud Service Account with appropriate permissions and API Keys.

## Setup Instructions

### Environment Variables
In the `Backend` directory, create a `.env` file containing your Google Cloud credentials:
```
GOOGLE_API_KEY=your_api_key_here
GOOGLE_PROJECT_ID=your_project_id_here
```
You will also need to configure your service account credentials for Google Cloud authentication as required by Vertex AI.

### Running the Backend Server
1. Navigate to the `Backend` folder.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the FastAPI server:
   ```bash
   uvicorn main:app --reload
   ```
   The backend mounts the static website, making it accessible at `http://localhost:8000/`.

### Using the Chrome Extension
1. Open Google Chrome and go to `chrome://extensions/`.
2. Enable "Developer mode" in the top right corner.
3. Click "Load unpacked" and select the `Frontend` folder.
4. The extension should now be installed and ready to test.

## How it Works

When text is submitted with a target language, the system operates as follows:
1. Detects the source language of the input text.
2. If the text is not in English, it translates it to English using Google Cloud Translation.
3. The English text is passed to the Gemini model via Vertex AI with a strict system prompt to generate a neutral, factual summary.
4. The requested summary is then translated from English into the final target language.
5. In the background, the system performs a quality evaluation by analyzing summary similarity and translation consistency.
