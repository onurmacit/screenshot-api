import NextAuth from "next-auth";
import GoogleProvider from "next-auth/providers/google";
import GitHubProvider from "next-auth/providers/github";
import axios from "axios";

const handler = NextAuth({
    providers: [
        GoogleProvider({
            clientId: process.env.GOOGLE_CLIENT_ID || "placeholder",
            clientSecret: process.env.GOOGLE_CLIENT_SECRET || "placeholder",
        }),
        GitHubProvider({
            clientId: process.env.GITHUB_ID || "placeholder",
            clientSecret: process.env.GITHUB_SECRET || "placeholder",
        }),
    ],
    callbacks: {
        async signIn({ user, account, profile }) {
            if (account && (account.provider === "google" || account.provider === "github")) {
                try {
                    const backendUrl = "http://127.0.0.1:8000";
                    const response = await axios.post(`${backendUrl}/api/v1/auth/social-login`, {
                        provider: account.provider,
                        token: account.id_token || account.access_token,
                        full_name: user.name
                    });

                    if (response.data.access_token) {
                        // @ts-ignore
                        user.accessToken = response.data.access_token;
                        return true;
                    }
                    return false;
                } catch (error) {
                    console.error("Social login backend error:", error);
                    return false;
                }
            }
            return true;
        },
        async jwt({ token, user, account }) {
            if (user) {
                token.id = user.id;
                // @ts-ignore
                token.accessToken = user.accessToken;
            }
            return token;
        },
        async session({ session, token }) {
            // @ts-ignore
            session.accessToken = token.accessToken;
            // @ts-ignore
            session.user.id = token.id;
            return session;
        },
    },
    pages: {
        signIn: "/login",
    },
    secret: process.env.NEXTAUTH_SECRET || "placeholder-secret",
});

export { handler as GET, handler as POST };
