export const poInboxLocators = {
  documentsMenu: {
    role: "link" as const,
    name: "Chứng từ",
  },
  inboxOrdersMenuItem: {
    role: "link" as const,
    name: "Inbox Đơn Đặt hàng",
  },
  inboxPageMarker: {
    title: /^Inbox Đơn Đặt Hàng$/i,
  },
  deliveryDateFrom: {
    selector: 'input[name="deliveryDateFrom"]',
  },
  deliveryDateTo: {
    selector: 'input[name="deliveryDateTo"]',
  },
  search: {
    text: "Tìm kiếm",
  },
  resultArea: {
    selector: "#content",
  },
  resultTable: {
    selector: "#table-content",
  },
  resultRow: {
    selector: 'tbody tr:has(input[type="checkbox"])',
  },
  resultTotal: {
    selector: 'input[name="total"]',
  },
  pageSize: {
    selector: 'input[name="aux.max"]',
  },
  selectAll: {
    title: "Select All",
  },
  selectableRowCheckbox: {
    selector: 'tbody tr:has(input[type="checkbox"]) input[type="checkbox"]:enabled',
  },
  batchPrint: {
    text: "In theo lô",
  },
  pagination: {
    nextPage: {
      text: "Tiếp theo",
    },
    currentPage: {
      selector: 'input[name="page"]',
    },
    totalRecords: {
      selector: 'input[name="total"]',
    },
    pageSize: {
      selector: 'input[name="aux.max"]',
    },
  },
};