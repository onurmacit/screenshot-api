import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
    baseURL: API_URL,
    headers: {
        "Content-Type": "application/json",
    },
});

// Request interceptor - add auth token
api.interceptors.request.use((config) => {
    if (typeof window !== "undefined") {
        const token = localStorage.getItem("token");
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
    }
    return config;
});

// Response interceptor - handle 401 errors (token expired/invalid)
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (typeof window !== "undefined" && error.response?.status === 401) {
            // Token expired or invalid - clear auth and redirect to login
            localStorage.removeItem("token");
            document.cookie = "token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
            
            // Only redirect if not already on login page
            if (!window.location.pathname.includes("/login")) {
                window.location.href = "/login?expired=true";
            }
        }
        return Promise.reject(error);
    }
);

// Helper function to check if JWT token is expired
export function isTokenExpired(token: string): boolean {
    try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        const exp = payload.exp;
        if (!exp) return false;
        // Add 10 second buffer to account for clock skew
        return Date.now() >= (exp * 1000) - 10000;
    } catch {
        return true; // If we can't parse the token, consider it expired
    }
}

// Helper function to get token expiration time in ms
export function getTokenExpirationTime(token: string): number | null {
    try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        return payload.exp ? payload.exp * 1000 : null;
    } catch {
        return null;
    }
}

// Types
export interface User {
    id: string;
    email: string;
    is_active: boolean;
    is_superuser: boolean;
}

export interface LoginResponse {
    access_token: string;
    token_type: string;
}

export interface APIKey {
    key_id: string;
    name: string;
    key_prefix: string;
    scopes: string[];
    last_used_at: string | null;
    created_at: string;
    expires_at: string | null;
    is_active: boolean;
}

export interface CreateAPIKeyResponse extends APIKey {
    api_key: string; // The full key, only returned on creation
}

export interface CreateAPIKeyRequest {
    name: string;
    scopes?: string[];
    expires_at?: string | null;
}

// Auth API
export const authApi = {
    login: async (username: string, password: string) => {
        const response = await api.post<LoginResponse>("/api/v1/auth/login", {
            email: username,
            password: password,
        });
        return response.data;
    },

    register: async (email: string, password: string, fullName: string) => {
        const response = await api.post("/api/v1/auth/register", {
            email,
            password,
            full_name: fullName,
        });
        return response.data;
    },

    getMe: async () => {
        try {
            const response = await api.get<User>("/api/v1/auth/test-token");
            return response.data;
        } catch {
            return null; // Handle error gracefully
        }
    },

    // API Keys Management
    listApiKeys: async () => {
        const response = await api.get<APIKey[]>("/api/v1/auth/api-keys");
        return response.data;
    },

    createApiKey: async (data: CreateAPIKeyRequest) => {
        const response = await api.post<CreateAPIKeyResponse>("/api/v1/auth/api-keys", data);
        return response.data;
    },

    deleteApiKey: async (keyId: string) => {
        await api.delete(`/api/v1/auth/api-keys/${keyId}`);
    },

    // Usage
    getUsageHistory: async (params?: { start_date?: string; end_date?: string; granularity?: string }) => {
        const response = await api.get<UsageHistoryResponse>("/api/v1/usage/history", { params });
        return response.data;
    }
};

export interface UsageHistoryResponse {
    start_date: string;
    end_date: string;
    granularity: string;
    usage: DailyUsage[];
    total_requests: number;
    total_processing_time_ms: number;
    total_file_size_bytes: number;
}

export interface DailyUsage {
    date: string;
    requests: number;
    screenshots: number;
    pdfs: number;
    total_processing_time_ms: number;
    total_file_size_bytes: number;
}
