import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";
import { getRawClient } from "./db";

const JWT_SECRET = process.env.JWT_SECRET || "your-secret-key";
const SALT_ROUNDS = 10;

/**
 * Hash a password using bcrypt
 */
export async function hashPassword(password: string): Promise<string> {
  return bcrypt.hash(password, SALT_ROUNDS);
}

/**
 * Verify a password against a hash
 */
export async function verifyPassword(password: string, hash: string): Promise<boolean> {
  return bcrypt.compare(password, hash);
}

export interface AuthUser {
  id: number;
  email: string;
  name: string | null;
  role: "user" | "admin";
}

export interface RegisterInput {
  email: string;
  password: string;
  name?: string;
}

export interface LoginInput {
  email: string;
  password: string;
}

/**
 * Register a new user with email and password
 */
export async function registerUser(input: RegisterInput): Promise<{ success: boolean; error?: string; user?: AuthUser; token?: string }> {
  const { email, password, name } = input;

  // Validate input
  if (!email || !password) {
    return { success: false, error: "メールアドレスとパスワードは必須です" };
  }

  if (password.length < 6) {
    return { success: false, error: "パスワードは6文字以上で入力してください" };
  }

  try {
    const sql = await getRawClient();
    if (!sql) {
      return { success: false, error: "データベース接続エラー" };
    }
    
    // Check if user already exists
    const existingUsers = await sql`SELECT id FROM users WHERE email = ${email} LIMIT 1`;
    
    if (existingUsers.length > 0) {
      return { success: false, error: "このメールアドレスは既に登録されています" };
    }

    // Hash password
    const passwordHash = await bcrypt.hash(password, SALT_ROUNDS);

    // Create user
    await sql`
      INSERT INTO users (email, password_hash, name, "loginMethod", role, "createdAt", "updatedAt", "lastSignedIn") 
      VALUES (${email}, ${passwordHash}, ${name || null}, 'local', 'user', NOW(), NOW(), NOW())
    `;

    // Get the newly created user
    const newUsers = await sql`SELECT id, email, name, role FROM users WHERE email = ${email} LIMIT 1`;

    if (newUsers.length === 0) {
      return { success: false, error: "ユーザーの作成に失敗しました" };
    }

    const newUser = newUsers[0];

    // Generate JWT token
    const token = jwt.sign(
      { userId: newUser.id, email: newUser.email, role: newUser.role },
      JWT_SECRET,
      { expiresIn: "30d" }
    );

    return {
      success: true,
      user: {
        id: newUser.id,
        email: newUser.email,
        name: newUser.name,
        role: newUser.role,
      },
      token,
    };
  } catch (error: any) {
    console.error("[Auth] Registration error:", error?.message || error);
    console.error("[Auth] Registration error stack:", error?.stack);
    return { success: false, error: `登録に失敗しました: ${error?.message || '不明なエラー'}` };
  }
}

/**
 * Login user with email and password
 */
export async function loginUser(input: LoginInput): Promise<{ success: boolean; error?: string; user?: AuthUser; token?: string }> {
  const { email, password } = input;

  // Validate input
  if (!email || !password) {
    return { success: false, error: "メールアドレスとパスワードは必須です" };
  }

  try {
    const sql = await getRawClient();
    if (!sql) {
      return { success: false, error: "データベース接続エラー" };
    }
    
    // Find user by email
    const users = await sql`SELECT id, email, name, role, password_hash FROM users WHERE email = ${email} LIMIT 1`;
    
    if (users.length === 0) {
      return { success: false, error: "メールアドレスまたはパスワードが正しくありません" };
    }

    const user = users[0];

    // Check password
    if (!user.password_hash) {
      return { success: false, error: "このアカウントはパスワードログインに対応していません" };
    }

    const isValidPassword = await bcrypt.compare(password, user.password_hash);
    if (!isValidPassword) {
      return { success: false, error: "メールアドレスまたはパスワードが正しくありません" };
    }

    // Update last signed in
    await sql`UPDATE users SET "lastSignedIn" = NOW() WHERE id = ${user.id}`;

    // Generate JWT token
    const token = jwt.sign(
      { userId: user.id, email: user.email, role: user.role },
      JWT_SECRET,
      { expiresIn: "30d" }
    );

    return {
      success: true,
      user: {
        id: user.id,
        email: user.email,
        name: user.name,
        role: user.role,
      },
      token,
    };
  } catch (error: any) {
    console.error("[Auth] Login error:", error?.message || error);
    return { success: false, error: "ログインに失敗しました" };
  }
}

/**
 * Verify JWT token and return user
 */
export async function verifyToken(token: string): Promise<AuthUser | null> {
  try {
    console.log('[Auth] Verifying token...');
    const decoded = jwt.verify(token, JWT_SECRET) as { userId: number; email: string; role: "user" | "admin" };
    console.log('[Auth] Token decoded:', decoded);
    
    const sql = await getRawClient();
    if (!sql) {
      console.log('[Auth] Database connection error');
      return null;
    }
    
    const users = await sql`SELECT id, email, name, role FROM users WHERE id = ${decoded.userId} LIMIT 1`;
    console.log('[Auth] Users found:', users.length);
    
    if (users.length === 0) {
      console.log('[Auth] No user found for userId:', decoded.userId);
      return null;
    }

    const user = users[0];
    console.log('[Auth] User found:', user);
    return {
      id: user.id,
      email: user.email,
      name: user.name,
      role: user.role,
    };
  } catch (error: any) {
    console.error('[Auth] Token verification error:', error?.message || error);
    return null;
  }
}

/**
 * Get user by ID
 */
export async function getUserById(userId: number): Promise<AuthUser | null> {
  try {
    const sql = await getRawClient();
    if (!sql) {
      return null;
    }
    
    const users = await sql`SELECT id, email, name, role FROM users WHERE id = ${userId} LIMIT 1`;
    
    if (users.length === 0) {
      return null;
    }

    const user = users[0];
    return {
      id: user.id,
      email: user.email,
      name: user.name,
      role: user.role,
    };
  } catch (error) {
    console.error("[Auth] Get user error:", error);
    return null;
  }
}
