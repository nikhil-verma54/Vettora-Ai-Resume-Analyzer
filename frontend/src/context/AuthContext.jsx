import { createContext, useContext, useEffect, useState, useCallback } from "react";
import {
  onAuthStateChanged,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  GoogleAuthProvider,
  signOut,
} from "firebase/auth";
import { auth } from "../config/firebase";

const AuthContext = createContext(null);
const googleProvider = new GoogleAuthProvider();

// =====================================================
// DJANGO BACKEND API URL
// Configurable via VITE_API_URL in production (Render)
// Defaults to empty string locally (Vite dev proxy)
// =====================================================
const API_URL = import.meta.env.VITE_API_URL || "";

// =====================================================
// AUTH PROVIDER
// =====================================================
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // =====================================================
  // SEND FIREBASE USER TO DJANGO
  // Used after Firebase login/register
  // =====================================================
  const sendTokenToDjango = async (firebaseUser) => {
    try {
      if (!firebaseUser) return null;

      // Get fresh Firebase ID token
      const idToken = await firebaseUser.getIdToken(true);

      // Send token to Django login endpoint
      const response = await fetch(`${API_URL}/api/auth/login/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        // Include credentials so Django can set/read session cookies
        credentials: "include",
        body: JSON.stringify({
          idToken: idToken,
        }),
      });

      if (!response.ok) {
        return null;
      }

      return await response.json();
    } catch {
      return null;
    }
  };

  // =====================================================
  // AUTHENTICATED DJANGO REQUEST
  // Used for dashboard, resume analysis, and interview APIs
  // =====================================================
  const djangoRequest = useCallback(async (endpoint, options = {}) => {
    const currentUser = auth.currentUser;
    if (!currentUser) {
      throw new Error("No authenticated user is currently logged in.");
    }

    // Get fresh Firebase ID token
    const idToken = await currentUser.getIdToken(true);
    if (!idToken) {
      throw new Error("Firebase ID token could not be obtained.");
    }

    const headers = new Headers(options.headers || {});
    headers.set("Authorization", `Bearer ${idToken}`);

    let body = options.body;
    if (body && !(body instanceof FormData) && typeof body === "object") {
      body = JSON.stringify(body);
    }

    // Only set Content-Type if a body exists, is not FormData,
    // and caller hasn't already specified it.
    if (body && !headers.has("Content-Type") && !(options.body instanceof FormData)) {
      headers.set("Content-Type", "application/json");
    }

    const response = await fetch(`${API_URL}${endpoint}`, {
      ...options,
      body,
      headers,
      credentials: "include",
    });

    const contentType = response.headers.get("content-type");
    let data;
    if (contentType && contentType.includes("application/json")) {
      data = await response.json();
    } else {
      data = await response.text();
    }

    if (!response.ok) {
      if (typeof data === "object") {
        throw new Error(data.detail || data.error || "Django request failed.");
      }
      throw new Error(data || "Django request failed.");
    }

    return data;
  }, []);

  // =====================================================
  // REGISTER
  // =====================================================
  const register = async (email, password) => {
    const result = await createUserWithEmailAndPassword(auth, email, password);
    await sendTokenToDjango(result.user);
    return result;
  };

  // =====================================================
  // EMAIL LOGIN
  // =====================================================
  const login = async (email, password) => {
    const result = await signInWithEmailAndPassword(auth, email, password);
    await sendTokenToDjango(result.user);
    return result;
  };

  // =====================================================
  // GOOGLE LOGIN
  // =====================================================
  const googleLogin = async () => {
    const result = await signInWithPopup(auth, googleProvider);
    await sendTokenToDjango(result.user);
    return result;
  };

  // =====================================================
  // LOGOUT
  // =====================================================
  const logout = async () => {
    await signOut(auth);
  };

  // =====================================================
  // AUTH STATE LISTENER
  // =====================================================
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (currentUser) => {
      setUser(currentUser);
      // Sync Django session/UserProfile every time Firebase auth state is
      // restored (page reload, re-login after logout, token refresh etc.)
      // This ensures the Django UserProfile always exists before API calls.
      if (currentUser) {
        try {
          await sendTokenToDjango(currentUser);
        } catch {
          // Non-fatal — djangoRequest still sends Bearer token on every call
        }
      }
      setLoading(false);
    });

    return () => unsubscribe();
  }, []);

  // =====================================================
  // CONTEXT VALUE
  // =====================================================
  const value = {
    user,
    loading,
    register,
    login,
    googleLogin,
    logout,
    djangoRequest,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// =====================================================
// CUSTOM HOOK
// =====================================================
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside an AuthProvider");
  }
  return context;
}
