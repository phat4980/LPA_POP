export const loginLocators = {
  username: {
    role: "textbox" as const,
    name: /username\s*\/\s*email/i,
  },
  password: {
    role: "textbox" as const,
    name: /password/i,
  },
  submit: {
    role: "button" as const,
    name: /login/i,
  },
};