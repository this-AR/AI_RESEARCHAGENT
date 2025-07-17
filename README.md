# AI Research Agent

A sophisticated multi-agent research automation system built with CrewAI that autonomously discovers leads, conducts comprehensive company research, and generates personalized outreach campaigns.

## Overview

The AI Research Agent leverages a multi-agent architecture to automate the entire lead discovery and outreach process. Using specialized AI agents with distinct roles, the system performs intelligent company research, analyzes market positioning, and creates highly personalized email campaigns optimized for engagement.

The system operates through a sequential workflow where each agent builds upon the previous agent's output, creating a comprehensive research and outreach pipeline that mimics human-level intelligence and coordination.

## Features

### 🤖 Multi-Agent Architecture
- **Lead Discovery Specialist**: Autonomous company research and intelligence gathering
- **Email Generation Specialist**: Personalized outreach content creation
- **Orchestration Manager**: Workflow coordination and optimization
- **Quality Assurance Specialist**: Output validation and engagement optimization

### 🔍 Advanced Research Capabilities
- Real-time web search integration via Serper API and DuckDuckGo
- Dynamic lead profiling with market positioning analysis
- Sentiment analysis for content optimization
- Company intelligence gathering and decision maker identification

### 📧 Intelligent Email Generation
- Personalized email sequence creation (4-email campaigns)
- Industry-specific language and terminology
- Value proposition alignment with company initiatives
- Mobile-optimized formatting with clear call-to-actions

### 🛠️ Custom Tool Integration
- Sentiment Analysis Module for engagement optimization
- Dynamic Lead Profiling Tool for comprehensive company analysis
- File Parsing Module for research data processing
- Multi-provider search integration (Serper API + DuckDuckGo fallback)

### ⚡ Performance Optimization
- Free-tier optimized with intelligent rate limiting
- Retry logic with exponential backoff for API calls
- Fallback mechanisms for robust operation
- Minimal token usage with smallest production models

## Tech Stack

- **Framework**: CrewAI Multi-Agent System
- **LLM Provider**: Groq API (Gemma-2-9B, Llama-3.1-8B models)
- **Search APIs**: Serper API (primary), DuckDuckGo (fallback)
- **Language**: Python 3.7+
- **Key Libraries**:
  - `crewai` - Multi-agent orchestration
  - `groq` - Fast LLM inference
  - `duckduckgo-search` - Free web search
  - `python-dotenv` - Environment management
  - `requests` - HTTP client

## Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/ai-research-agent.git
cd ai-research-agent
```

### 2. Install Dependencies
```bash
pip install crewai crewai[tools] python-dotenv requests groq duckduckgo-search
```

### 3. API Configuration

#### Groq API (Free Tier)
1. Sign up at [console.groq.com](https://console.groq.com/)
2. Generate a free API key
3. Update the `GROQ_API_KEY` in the configuration cell

#### Serper API (Optional - for enhanced search)
1. Sign up at [serper.dev](https://serper.dev/)
2. Get your API key
3. Update the `SERPER_API_KEY` in the configuration cell

### 4. Environment Variables
```python
os.environ["GROQ_API_KEY"] = "your_groq_api_key_here"
os.environ["SERPER_API_KEY"] = "your_serper_api_key_here"  # Optional
```

## Usage Instructions

### Basic Usage

1. **Configure Target Company**:
```python
target_company = {
    "company_name": "YourTargetCompany",
    "industry": "Technology",
    "key_decision_maker": "CEO Name",
    "position": "Chief Executive Officer",
    "recent_milestone": "recent company achievement"
}
```

2. **Execute Research Pipeline**:
```python
result = run_research_agent(target_company)
```

3. **Access Results**:
- Results are automatically saved to timestamped files
- Console output provides real-time progress updates
- QA validation ensures output quality before delivery

### Advanced Configuration

#### Model Selection
```python
def get_groq_model():
    production_models = [
        "gemma2-9b-it",              # Fastest, most economical
        "llama-3.1-8b-instant",      # Backup option
        "llama-3.3-70b-versatile"    # Higher capability
    ]
    return production_models[0]
```

#### Rate Limiting
```python
ai_research_crew = Crew(
    max_rpm=1,  # Requests per minute for free tier
    # ... other configuration
)
```

### System Testing
```python
# Test system components without API calls
test_system_offline()
```

## Customization

### Adding New Tools
```python
class CustomTool(BaseTool):
    name: str = "Custom Tool Name"
    description: str = "Tool description"
    
    def _run(self, input_data: str) -> str:
        # Your custom logic here
        return processed_result
```

### Modifying Agent Roles
```python
custom_agent = Agent(
    role="Your Custom Role",
    goal="Specific objective for this agent",
    backstory="Agent's expertise and background",
    tools=[your_tools],
    max_iter=3
)
```

### Customizing Email Templates
Modify the `personalized_email_task` description to adjust:
- Email sequence structure
- Personalization requirements
- Content tone and style
- Call-to-action formats

### Search Provider Configuration
```python
# Prioritize different search providers
if os.environ.get('CUSTOM_SEARCH_API'):
    search_tool = CustomSearchTool()
elif os.environ.get('SERPER_API_KEY'):
    search_tool = SerperDevTool()
else:
    search_tool = DuckDuckGoSearchTool()
```

## Limitations

### API Rate Limits
- **Groq Free Tier**: Limited requests per minute
- **Serper API**: 100 free searches per month
- **DuckDuckGo**: No official rate limits but may throttle

### Model Constraints
- Free tier models have smaller context windows
- Response quality varies with model size
- Token usage affects processing speed

### Data Accuracy
- Web search results may contain outdated information
- Lead profiling depends on publicly available data
- Company information accuracy varies by source

### Technical Dependencies
- Requires stable internet connection
- API availability affects system functionality
- Python 3.7+ required for compatibility

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## Support

For support and questions:
- Create an issue in the GitHub repository
- Check the documentation in the notebook comments
- Review the system testing functions for troubleshooting

## Acknowledgments

- [CrewAI](https://github.com/joaomdmoura/crewAI) for the multi-agent framework
- [Groq](https://groq.com/) for fast and efficient LLM inference
- [Serper](https://serper.dev/) for reliable web search capabilities
- The open-source community for the underlying tools and libraries

---

=======
# AI_RESEARCHAGENT
>>>>>>> 01b678f612168c289dbb51cfeaa4a991e5627606
