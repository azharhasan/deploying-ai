# Nobel Prize Physics Chat Assistant

A conversational AI chatbot that helps users explore the history of Nobel Prizes in Physics using OpenAI's GPT models, ChromaDB vector database, and Gradio interface.

## Overview

This application allows users to interact with a comprehensive database of Physics Nobel Prize laureates from 1901 to 2025 as well as the nobel prize API: https://www.nobelprize.org/about/developer-zone-2/. Users can ask questions about:
- Specific Nobel Prize winners and their years
- Research fields and the prizes awarded for them
- Motivations behind Nobel Prize awards
- Historical trends in Physics Nobel Prizes

### Components

1. **Gradio UI**: Web-based chat interface for user interactions
2. **OpenAI**: Language model for understanding queries and generating responses
3. **ChromaDB**: Vector database for semantic search over Nobel Prize data
4. **OpenAI Embeddings**: Text embeddings (text-embedding-3-small) for semantic similarity
5. **Function Calling**: Tool-use capabilities for structured data retrieval

### Data Flow

```
User Query → Gradio Interface → OpenAI GPT-4o-mini 
                                        ↓
                              Function Calling Decision
                                        ↓
                    ┌───────────────────┴───────────────────┐
                    ↓                                       ↓
         get_nobel_laureate_details()                get_nobel_history()
         (Query by specific year)              (Semantic search by research field)
                    ↓                                       ↓
              Direct API lookup                    ChromaDB Vector Search
                    ↓                                       ↓
                    └───────────────────┬───────────────────┘
                                        ↓
                              Format & Return Results
                                        ↓
                              OpenAI GPT-4o-mini
                                        ↓
                            Natural Language Response
                                        ↓
                              Gradio Interface → User
```

## Features

### 1. **Year-Based Lookup**
Query Nobel Prize winners by specific year:
- *"Tell me about the 1921 Nobel Prize in Physics"*

Uses Nobel Prize API to fetch motivation for Nobel Prize in Physics for a particular year

### 2. **Semantic Research Field Search**
Search by research topics using vector similarity:
- *"What prizes have been given in quantum mechanics?"*
- *"Show me Nobel Prizes related to black holes"*
- *"List prizes for particle physics research"*

Before searching, the app extracts the core research topic:
```
User: "Tell me about prizes given for work on lasers and optical stuff"
Extracted: "laser physics and optical research"
→ Searches for relevant prizes
```

The app uses vector embeddings to understand the *meaning* of queries:
- "quantum mechanics" matches prizes for quantum theory, quantum computing, etc.
- "space" matches cosmology, astrophysics, black holes, etc.
- More intelligent than keyword matching
