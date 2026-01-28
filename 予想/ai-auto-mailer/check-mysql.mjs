import mysql from 'mysql2/promise';

const DATABASE_URL = process.env.DATABASE_URL;
if (!DATABASE_URL) {
  console.error('DATABASE_URL not set');
  process.exit(1);
}

async function main() {
  const connection = await mysql.createConnection({
    uri: DATABASE_URL,
    ssl: { rejectUnauthorized: true }
  });
  try {
    const [rows] = await connection.execute('SHOW COLUMNS FROM users');
    console.log('Columns:');
    rows.forEach(r => console.log(`  - ${r.Field}: ${r.Type}`));
  } catch (e) {
    console.error('Error:', e.message);
  } finally {
    await connection.end();
  }
}

main();
