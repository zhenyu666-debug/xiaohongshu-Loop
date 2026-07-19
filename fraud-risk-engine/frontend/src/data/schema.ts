// TigerGraph Entity Resolution MDM starter-kit schema
// (mirrors video: Account + feature vertices + VideoPlay intermediate)

export interface VertexType {
  name: string;
  attributes: { name: string; type: string }[];
  isCenter?: boolean;
}

export interface EdgeType {
  name: string;
  from: string;
  to: string;
  directed: boolean;
}

export const VERTEX_TYPES: VertexType[] = [
  {
    name: "Account",
    isCenter: true,
    attributes: [
      { name: "account_id", type: "STRING" },
      { name: "first_name", type: "STRING" },
      { name: "middle_name", type: "STRING" },
      { name: "last_name", type: "STRING" },
      { name: "email", type: "STRING" },
      { name: "phone", type: "STRING" },
      { name: "address", type: "STRING" },
      { name: "city", type: "STRING" },
      { name: "state", type: "STRING" },
      { name: "zip", type: "STRING" },
      { name: "country", type: "STRING" },
      { name: "registration_date", type: "STRING" },
      { name: "account_type", type: "STRING" },
      { name: "status", type: "STRING" },
      { name: "risk_score", type: "DOUBLE" },
    ],
  },
  {
    name: "IP",
    attributes: [
      { name: "ip", type: "STRING" },
      { name: "city", type: "STRING" },
      { name: "state", type: "STRING" },
      { name: "country", type: "STRING" },
    ],
  },
  {
    name: "Email",
    attributes: [
      { name: "email", type: "STRING" },
      { name: "domain", type: "STRING" },
    ],
  },
  {
    name: "LastName",
    attributes: [{ name: "last_name", type: "STRING" }],
  },
  {
    name: "Phone",
    attributes: [{ name: "phone", type: "STRING" }],
  },
  {
    name: "Address",
    attributes: [
      { name: "address", type: "STRING" },
      { name: "city", type: "STRING" },
      { name: "state", type: "STRING" },
      { name: "zip", type: "STRING" },
    ],
  },
  {
    name: "Device",
    attributes: [
      { name: "device_id", type: "STRING" },
      { name: "device_type", type: "STRING" },
      { name: "os", type: "STRING" },
    ],
  },
  {
    name: "VideoPlay",
    attributes: [
      { name: "play_id", type: "STRING" },
      { name: "video_id", type: "STRING" },
      { name: "ts", type: "STRING" },
      { name: "watch_time_secs", type: "INT" },
    ],
  },
  {
    name: "Video",
    attributes: [
      { name: "video_id", type: "STRING" },
      { name: "title", type: "STRING" },
      { name: "duration_secs", type: "INT" },
      { name: "category", type: "STRING" },
    ],
  },
  // For entity resolution
  {
    name: "MergedAccount",
    attributes: [{ name: "id", type: "STRING" }],
  },
];

export const EDGE_TYPES: EdgeType[] = [
  { name: "HAS_IP", from: "Account", to: "IP", directed: true },
  { name: "HAS_EMAIL", from: "Account", to: "Email", directed: true },
  { name: "HAS_LASTNAME", from: "Account", to: "LastName", directed: true },
  { name: "HAS_PHONE", from: "Account", to: "Phone", directed: true },
  { name: "HAS_ADDRESS", from: "Account", to: "Address", directed: true },
  { name: "HAS_DEVICE", from: "Account", to: "Device", directed: true },
  { name: "PLAYS_VIDEO", from: "Account", to: "VideoPlay", directed: true },
  { name: "VIDEO_PLAYED", from: "VideoPlay", to: "Video", directed: true },
  { name: "SAME_OWNER", from: "Account", to: "Account", directed: false },
  { name: "MERGED_INTO", from: "Account", to: "MergedAccount", directed: true },
];

export const FEATURE_EDGE_NAMES = [
  "HAS_IP",
  "HAS_EMAIL",
  "HAS_LASTNAME",
  "HAS_PHONE",
  "HAS_ADDRESS",
  "HAS_DEVICE",
];

export const EDGE_SCORES: Record<string, number> = {
  HAS_IP: 0.2,
  HAS_EMAIL: 0.3,
  HAS_LASTNAME: 0.3,
  HAS_PHONE: 0.2,
  HAS_ADDRESS: 0.1,
  HAS_DEVICE: 0.2,
};
