// User state management (simplified version without authentication)

export function useUserStore() {
  // Default to logged-in state
  const isLoggedIn = true
  const user = {
    id: 'admin',
    username: 'admin',
    name: 'Admin'
  }

  // Get empty auth headers (no authentication required)
  const getAuthHeaders = () => {
    return {}
  }

  // Empty login function (maintain interface compatibility)
  const login = async (_username: string, _password: string): Promise<boolean> => {
    return true
  }

  // Empty logout function (maintain interface compatibility)
  const logout = () => {
    // Do nothing
  }

  return {
    user,
    isLoggedIn,
    getAuthHeaders,
    login,
    logout
  }
}
