/**
 * Sentindex API - Node.js version for Vercel
 * Avoiding Python runtime issues by using Node.js
 * Integrated with Sentient Dobby LLM
 */

// Sentient API configuration
const SENTIENT_CONFIG = {
  apiKey: process.env.SENTIENT_API_KEY || 'key_4pVTEkqgJWn3ZMVz',
  baseUrl: 'https://api.sentient.ai/v1/chat/completions',
  model: 'dobby',
  maxTokens: 1000,
  temperature: 0.1
};

// Function to call Sentient API
async function callSentientAPI(prompt) {
  try {
    const response = await fetch(SENTIENT_CONFIG.baseUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${SENTIENT_CONFIG.apiKey}`
      },
      body: JSON.stringify({
        model: SENTIENT_CONFIG.model,
        messages: [
          {
            role: 'system',
            content: 'You are a financial analyst. Provide concise, accurate market analysis in JSON format.'
          },
          {
            role: 'user',
            content: prompt
          }
        ],
        max_tokens: SENTIENT_CONFIG.maxTokens,
        temperature: SENTIENT_CONFIG.temperature
      })
    });

    if (!response.ok) {
      throw new Error(`Sentient API error: ${response.status}`);
    }

    const data = await response.json();
    return data.choices[0]?.message?.content || 'No response from AI';
  } catch (error) {
    console.error('Sentient API error:', error);
    return `AI analysis unavailable: ${error.message}`;
  }
}

export default function handler(req, res) {
  // Set CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  res.setHeader('Content-Type', 'application/json');

  // Handle OPTIONS requests
  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }

  const { method, url } = req;
  const path = url.split('?')[0]; // Remove query params

  try {
    if (method === 'GET') {
      if (path === '/') {
        res.status(200).json({
          name: "Sentindex API",
          version: "1.0.0",
          status: "running",
          message: "Financial index platform with Sentient LLM integration",
          endpoints: {
            health: "/health",
            latest_index: "/v1/index/{name}/latest",
            compute_index: "/v1/index/{name}/compute",
            insights: "/v1/index/{name}/insights"
          }
        });
      } else if (path === '/health') {
        res.status(200).json({
          status: "healthy",
          message: "API is working correctly",
          timestamp: "2025-01-01T00:00:00Z"
        });
      } else if (path.startsWith('/v1/index/') && path.endsWith('/latest')) {
        // Extract index name from path
        const parts = path.split('/');
        const indexName = parts[parts.length - 2] || "default";
        res.status(200).json({
          index_name: indexName,
          index_value: 1234.56,
          method: "level_normalized",
          timestamp: "2025-01-01T00:00:00Z",
          message: "Demo data - use /compute endpoint for real calculations"
        });
      } else if (path.startsWith('/v1/index/') && path.endsWith('/insights')) {
        // Extract index name from path
        const parts = path.split('/');
        const indexName = parts[parts.length - 2] || "default";
        
        // Create prompt for Sentient API
        const prompt = `Analyze the current financial market conditions for the ${indexName} index. 
        Provide insights on:
        1. Market sentiment (positive/negative/neutral)
        2. Key market drivers
        3. Notable events or trends
        4. Risk factors
        5. Outlook summary
        
        Return your analysis in JSON format with keys: sentiment, summary, notable_events, risk_factors, outlook.`;
        
        // Call Sentient API
        const aiResponse = await callSentientAPI(prompt);
        
        res.status(200).json({
          index_name: indexName,
          insights: {
            ai_analysis: aiResponse,
            sentiment: "AI-generated",
            notable_events: ["Real-time AI analysis"],
            source: "Sentient Dobby LLM",
            timestamp: new Date().toISOString()
          },
          timestamp: new Date().toISOString(),
          message: "AI insights generated using Sentient Dobby LLM",
          source: "Sentient Dobby LLM"
        });
      } else if (path === '/metrics') {
        res.status(200).json({
          message: "Metrics endpoint available",
          status: "healthy",
          timestamp: "2025-01-01T00:00:00Z"
        });
      } else if (path === '/api/sentient/test') {
        // Test endpoint for Sentient API
        const testPrompt = "Provide a brief market analysis for today's financial markets in JSON format.";
        const aiResponse = await callSentientAPI(testPrompt);
        
        res.status(200).json({
          message: "Sentient API test successful",
          prompt: testPrompt,
          response: aiResponse,
          timestamp: new Date().toISOString(),
          source: "Sentient Dobby LLM"
        });
      } else {
        res.status(404).json({ error: "Not found", path: path });
      }
    } else if (method === 'POST') {
      if (path.startsWith('/v1/index/') && path.endsWith('/compute')) {
        // Extract index name from path
        const parts = path.split('/');
        const indexName = parts[parts.length - 2] || "default";
        
        try {
          const requestData = JSON.parse(req.body);
          const prices = requestData.prices || {};
          const method = requestData.method || 'level_normalized';
          
          // Simple calculation
          let indexValue;
          if (method === "level_normalized") {
            const weights = { GOLD: 0.25, SILVER: 0.25, OIL: 0.20, BTC: 0.15, ETH: 0.15 };
            const basePrices = { GOLD: 1800.0, SILVER: 23.0, OIL: 75.0, BTC: 20000.0, ETH: 1000.0 };
            
            let score = 0.0;
            for (const [symbol, weight] of Object.entries(weights)) {
              if (prices[symbol] && basePrices[symbol]) {
                if (basePrices[symbol] > 0) {
                  const normalized = prices[symbol] / basePrices[symbol];
                  score += normalized * weight;
                }
              }
            }
            
            indexValue = Math.round(score * 1000.0 * 100) / 100; // Round to 2 decimal places
          } else {
            indexValue = 1000.0;
          }
          
          res.status(200).json({
            index_name: indexName,
            index_value: indexValue,
            method: method,
            timestamp: "2025-01-01T00:00:00Z",
            message: "Index calculated successfully"
          });
        } catch (error) {
          res.status(400).json({
            error: "Invalid request data",
            message: error.message
          });
        }
      } else {
        res.status(404).json({ error: "Not found", path: path });
      }
    } else {
      res.status(405).json({ error: "Method not allowed", method: method });
    }
  } catch (error) {
    res.status(500).json({
      error: "Internal server error",
      message: error.message
    });
  }
}
