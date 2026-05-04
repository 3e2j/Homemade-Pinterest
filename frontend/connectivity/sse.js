/** Parse Server-Sent Events stream and call callback for each message */
export async function parseSSEStream(response, onMessage) {
  if (!response.ok) throw new Error("SSE stream failed");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const text = decoder.decode(value);
      const lines = text.split("\n");

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.slice(6));
            onMessage(data);
          } catch (e) {
            // Ignore parsing errors on invalid JSON
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
