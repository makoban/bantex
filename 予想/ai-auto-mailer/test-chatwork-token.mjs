const token = process.env.CHATWORK_API_TOKEN;
console.log("Token set:", !!token);
console.log("Token length:", token ? token.length : 0);
console.log("Token (masked):", token ? token.substring(0, 8) + "..." : "NOT SET");

try {
  const response = await fetch("https://api.chatwork.com/v2/me", {
    headers: { "X-ChatworkToken": token },
  });
  const data = await response.json();
  console.log("API Response:", data);
} catch (e) {
  console.error("Error:", e);
}
