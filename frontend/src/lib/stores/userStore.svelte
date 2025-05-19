<script context="module" lang="ts">
        // script block runs once when the module is imported
        
        import { writable } from 'svelte/store';
        
        // --- User Interface Definition ---
        export interface User {
                loggedIn: boolean;
                email?: string;
                username?: string;
                userID?: string;
                role?: string;
        }
        
        // --- Initial State ---
        const initialUser: User | null = null;
        
        // --- Svelte Writable Store ---
        // subscribable by other components
        export const userStore = writable<User | null>(initialUser);
        
        // --- Fetch User Status Action ---
        // gets user status from backend
        export async function fetchUserStatus() {
                try {
                        const response = await fetch('/api/me');
                        
                        if (response.ok) {
                                const userDataFromApi = await response.json();
                                if (userDataFromApi && userDataFromApi.loggedIn) {
                                        userStore.set({
                                                loggedIn: true,
                                                email: userDataFromApi.email,
                                                username: userDataFromApi.username,
                                                userID: userDataFromApi.userID,
                                                role: userDataFromApi.role
                                        });
                                } else {
                                        userStore.set(null);
                                }
                        } else {
                                console.error('Failed to fetch user status from API:', response.status, response.statusText);
                                userStore.set(null);
                        }
                } catch (error) {
                        console.error('Error fetching user status:', error);
                        userStore.set(null);
                }
        }
        
        // --- Clear User Function : UNUSED CURRENTLY ---
        export function clearUser() {
                userStore.set(null);
        }
</script>