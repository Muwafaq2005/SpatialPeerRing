import express from 'express';
import path from 'path';
import dotenv from 'dotenv';
import { fileURLToPath } from 'url';
import { GoogleGenAI, Type } from '@google/genai';
import { createServer as createViteServer } from 'vite';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config({ path: path.resolve(__dirname, '../.env') });
dotenv.config({ path: path.resolve(__dirname, '.env') });

const app = express();
const PORT = 3000;

app.use(express.json());

// Initialize Gemini SDK lazily
function getGeminiClient() {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    return null;
  }
  return new GoogleGenAI({
    apiKey,
    httpOptions: {
      headers: {
        'User-Agent': 'aistudio-build',
      },
    },
  });
}

// Health check
app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok', time: new Date().toISOString() });
});

// Real-time Collaborative Classroom Discussion Endpoint
app.post('/api/classroom/respond', async (req, res) => {
  try {
    const { topic = null, userQuery, history = [] } = req.body;
    const topicContext = topic ? `Current Topic: "${topic}"` : 'Current Topic: None / Unspecified (Determine from student question)';

    if (!userQuery || typeof userQuery !== 'string') {
      res.status(400).json({ error: 'User query is required.' });
      return;
    }

    console.log(`\n======================================================`);
    console.log(`[GROQ AI REQUEST] Topic: "${topic}" | Query: "${userQuery}"`);
    console.log(`======================================================`);

    const groqKey = process.env.GROQ_API_KEY || '';
    const groqModel = process.env.GROQ_MODEL || 'qwen/qwen3.8-27b';

    if (groqKey) {
      try {
        console.log(`[GROQ AI] Dispatching request to Groq model: ${groqModel}...`);
        const response = await fetch('https://api.groq.com/openai/v1/chat/completions', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${groqKey}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            model: groqModel,
            response_format: { type: 'json_object' },
            messages: [
              {
                role: 'system',
                content: `You are orchestrating an interactive 3D collaborative educational session with three AI participants:
- "charlie": AI Student seated on the right. Often shares a common student doubt or misconception.
- "alice": AI Peer Student at desk 1 (left). Provides hints, helpful analogies, and connects ideas.
- "bob": AI Tutor / Teacher at the chalkboard. Explains clearly, points to board, validates insights, and updates the blackboard.

Return ONLY a valid JSON object matching this schema:
{
  "blackboard": {
    "title": "Short blackboard header",
    "bullets": ["2 to 4 chalk bullet points or equations"],
    "diagramType": "free_body" | "trajectory" | "energy_graph" | "flowchart" | "formula_box" | "atoms" | "circuit",
    "diagramNote": "Brief chalk annotation or formula"
  },
  "dialogue": [
    {
      "speaker": "charlie" | "alice" | "bob",
      "speakerName": "Charlie (Classmate)" | "Alice (Classmate)" | "Bob (AI Tutor)",
      "text": "1-3 concise sentences for speech bubble",
      "emotion": "thinking" | "mistake_realization" | "hinting" | "explaining" | "pointing_board" | "celebrating",
      "gesture": "raise_hand" | "lean_forward" | "point_chalkboard" | "nod" | "confused_tilt"
    }
  ],
  "takeawaySummary": "One key takeaway summary"
}`
              },
              {
                role: 'user',
                content: `${topicContext}\nStudent Question: "${userQuery}"\nRecent Context: ${JSON.stringify(history.slice(-4))}`
              }
            ],
            temperature: 0.7,
          })
        });

        if (response.ok) {
          const jsonRes = await response.json();
          const rawContent = jsonRes.choices?.[0]?.message?.content || '{}';
          console.log(`[GROQ AI RESPONSE SUCCESS]:\n${rawContent}\n`);
          const parsed = JSON.parse(rawContent);
          res.json(parsed);
          return;
        } else {
          const errText = await response.text();
          console.warn(`[GROQ API WARN] Status ${response.status}: ${errText}`);
        }
      } catch (err) {
        console.error('[GROQ API ERROR]:', err);
      }
    }

    const ai = getGeminiClient();
    if (!ai) {
      console.log('[GROQ/GEMINI FALLBACK] Using pedagogical fallback simulation generator.');
      const fallbackResponse = generatePedagogicalFallback(topic || 'Unspecified Topic', userQuery, history);
      res.json(fallbackResponse);
      return;
    }

    const prompt = `
${topicContext}
User / Student Question or Doubt: "${userQuery}"
Recent Classroom Context: ${history.slice(-4).map((h: { speaker: string; text: string }) => `${h.speaker}: ${h.text}`).join('\n')}
`;

    const systemInstruction = `
You are orchestrating an interactive 3D collaborative educational session with three AI participants:
- "bob": The AI Tutor / Teacher standing near the blackboard.
- "alice": AI Peer Student at desk 1 (left).
- "charlie": AI Peer Student at desk 2 (right).
`;

    const modelName = process.env.GEMINI_MODEL || 'gemini-2.5-flash';
    const result = await ai.models.generateContent({
      model: modelName,
      contents: prompt,
      config: {
        systemInstruction,
        temperature: 0.7,
        responseMimeType: 'application/json',
      },
    });

    const parsed = JSON.parse(result.text || '{}');
    console.log('[GEMINI AI RESPONSE SUCCESS]:', parsed);
    res.json(parsed);
  } catch (err: unknown) {
    console.error('Error generating classroom response:', err);
    const fallback = generatePedagogicalFallback(req.body.topic || 'General Science', req.body.userQuery || 'Doubt', []);
    res.json(fallback);
  }
});

// Smart pedagogical fallback generator
function generatePedagogicalFallback(topic: string, query: string, _history: unknown[]) {
  const q = query.toLowerCase();
  if (q.includes('gravity') || q.includes('mass') || q.includes('fall') || q.includes('weight')) {
    return {
      blackboard: {
        title: 'Gravitational Acceleration & Mass',
        bullets: [
          'F_grav = G * (m1 * m2) / r²',
          'a = F / m  ==>  a = g = 9.81 m/s²',
          'Mass cancels out in free fall acceleration!',
          'Air resistance is what slows feather vs hammer',
        ],
        diagramType: 'free_body',
        diagramNote: 'm_heavy: [2F] / [2m] = g  |  m_light: [F] / [m] = g',
      },
      dialogue: [
        {
          speaker: 'charlie',
          speakerName: 'Charlie (Classmate)',
          text: 'Wait, I used to think a 10kg bowling ball MUST fall faster than a 1kg ball because the earth pulls it with 10x more force!',
          emotion: 'confused',
          gesture: 'confused_tilt',
        },
        {
          speaker: 'alice',
          speakerName: 'Alice (Classmate)',
          text: "Remember Newton's second law! Even though the gravitational pull is 10x stronger, the 10kg ball also has 10x more inertia to resist moving.",
          emotion: 'hinting',
          gesture: 'lean_forward',
        },
        {
          speaker: 'bob',
          speakerName: 'Bob (AI Tutor)',
          text: 'Brilliant insight from both of you! Charlie just raised the most famous historical misconception that Aristotle held for 2,000 years until Galileo corrected it. As Alice noted, inertia perfectly cancels the extra gravitational pull!',
          emotion: 'pointing_board',
          gesture: 'point_chalkboard',
        },
      ],
      takeawaySummary: 'All objects in vacuum accelerate at g = 9.8 m/s² regardless of mass because inertia balances gravitational force.',
    };
  }

  return {
    blackboard: {
      title: `${topic}: Core Analysis`,
      bullets: [
        `Key Question: "${query.slice(0, 45)}..."`,
        'Step 1: Identify fundamental principles & variables',
        'Step 2: Check boundary cases and common assumptions',
        'Takeaway: Verify using foundational laws',
      ],
      diagramType: 'flowchart',
      diagramNote: 'Intuition -> Test Assumption -> Verified Truth',
    },
    dialogue: [
      {
        speaker: 'charlie',
        speakerName: 'Charlie (Classmate)',
        text: "That's a tricky point! My first guess would have been the opposite, but let me think if that breaks any conservation rules...",
        emotion: 'thinking',
        gesture: 'confused_tilt',
      },
      {
        speaker: 'alice',
        speakerName: 'Alice (Classmate)',
        text: 'Here is a quick hint: break the problem into the initial state and the final state, and see what remains constant!',
        emotion: 'hinting',
        gesture: 'nod',
      },
      {
        speaker: 'bob',
        speakerName: 'Bob (AI Tutor)',
        text: `Great question regarding ${topic}! Bob here: Charlie's instinct is a very common starting point, while Alice gives us the exact analytical path. Let's look at the blackboard where I broke down the sequence!`,
        emotion: 'explaining',
        gesture: 'point_chalkboard',
      },
    ],
    takeawaySummary: `Deepened understanding of ${topic} through collaborative peer questioning and tutor blackboard synthesis.`,
  };
}

async function startServer() {
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (_req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`Classroom server running on http://0.0.0.0:${PORT}`);
  });
}

startServer();
