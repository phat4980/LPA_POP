export const purchaseOrderLocators = {
  deliveryDate: {
    label: "Delivery date",
  },
  selectAll: {
    role: "checkbox" as const,
    name: /select all/i,
  },
  print: {
    role: "button" as const,
    name: /print|in/i,
  },
  nextPage: {
    role: "button" as const,
    name: /next|下一页/i,
  },
};
