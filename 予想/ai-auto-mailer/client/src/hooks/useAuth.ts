import { trpc } from "@/lib/trpc";

export function useAuth() {
  const { data: user, isLoading, error, refetch } = trpc.localAuth.me.useQuery();
  
  const logoutMutation = trpc.localAuth.logout.useMutation({
    onSuccess: () => {
      // Reload to clear auth state
      window.location.href = "/login";
    },
  });

  return {
    user,
    isLoading,
    isAuthenticated: !!user,
    error,
    logout: () => logoutMutation.mutate(),
    refetch,
  };
}
