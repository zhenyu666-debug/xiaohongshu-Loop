// Mock graph data — realistic sample matching video Entity Resolution use-case

export interface GraphNode {
  id: string;
  type: string;
  label: string;
  properties: Record<string, string | number>;
  // D3 force layout
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  score?: number;
}

export const MOCK_NODES: GraphNode[] = [
  // Accounts (center nodes — larger)
  { id: "A001", type: "Account", label: "Account A001", properties: { first_name: "John", last_name: "Smith", email: "jsmith@example.com", status: "active" } },
  { id: "A002", type: "Account", label: "Account A002", properties: { first_name: "John", last_name: "Smith", email: "jsmith2@example.com", status: "active" } },
  { id: "A003", type: "Account", label: "Account A003", properties: { first_name: "Jane", last_name: "Doe", email: "janedoe@example.com", status: "active" } },
  { id: "A004", type: "Account", label: "Account A004", properties: { first_name: "Bob", last_name: "Johnson", email: "bjohnson@example.com", status: "active" } },
  { id: "A005", type: "Account", label: "Account A005", properties: { first_name: "Alice", last_name: "Brown", email: "abrown@example.com", status: "active" } },
  { id: "A006", type: "Account", label: "Account A006", properties: { first_name: "Carol", last_name: "Davis", email: "cdavis@example.com", status: "active" } },
  // Feature nodes
  { id: "IP1", type: "IP", label: "IP 192.168.1.1", properties: { ip: "192.168.1.1", city: "New York", country: "US" } },
  { id: "IP2", type: "IP", label: "IP 10.0.0.5", properties: { ip: "10.0.0.5", city: "Los Angeles", country: "US" } },
  { id: "IP3", type: "IP", label: "IP 172.16.0.1", properties: { ip: "172.16.0.1", city: "Chicago", country: "US" } },
  { id: "EM1", type: "Email", label: "Email jsmith@example.com", properties: { email: "jsmith@example.com", domain: "example.com" } },
  { id: "EM2", type: "Email", label: "Email jdoe@example.com", properties: { email: "jdoe@example.com", domain: "example.com" } },
  { id: "LN1", type: "LastName", label: "LastName Smith", properties: { last_name: "Smith" } },
  { id: "LN2", type: "LastName", label: "LastName Doe", properties: { last_name: "Doe" } },
  { id: "PH1", type: "Phone", label: "Phone 555-0101", properties: { phone: "555-0101" } },
  { id: "PH2", type: "Phone", label: "Phone 555-0202", properties: { phone: "555-0202" } },
  { id: "AD1", type: "Address", label: "Address 123 Main St", properties: { address: "123 Main St", city: "New York", state: "NY" } },
  { id: "AD2", type: "Address", label: "Address 456 Oak Ave", properties: { address: "456 Oak Ave", city: "Chicago", state: "IL" } },
  { id: "DV1", type: "Device", label: "Device MacBook Pro", properties: { device_id: "DEV001", device_type: "laptop", os: "macOS" } },
  { id: "DV2", type: "Device", label: "Device iPhone 15", properties: { device_id: "DEV002", device_type: "phone", os: "iOS" } },
  { id: "DV3", type: "Device", label: "Device Pixel 8", properties: { device_id: "DEV003", device_type: "phone", os: "Android" } },
  // VideoPlay intermediate nodes
  { id: "VP1", type: "VideoPlay", label: "VideoPlay VP1", properties: { play_id: "VP1", video_id: "V001", watch_time_secs: 120 } },
  { id: "VP2", type: "VideoPlay", label: "VideoPlay VP2", properties: { play_id: "VP2", video_id: "V002", watch_time_secs: 90 } },
  { id: "VP3", type: "VideoPlay", label: "VideoPlay VP3", properties: { play_id: "VP3", video_id: "V001", watch_time_secs: 200 } },
  // Videos
  { id: "V001", type: "Video", label: "Video: TigerGraph Tutorial", properties: { video_id: "V001", title: "TigerGraph Tutorial", duration_secs: 600, category: "Education" } },
  { id: "V002", type: "Video", label: "Video: Graph DB Deep Dive", properties: { video_id: "V002", title: "Graph DB Deep Dive", duration_secs: 900, category: "Technology" } },
  // MergedAccount (entity resolution result)
  { id: "MA001", type: "MergedAccount", label: "MergedAccount MA001", properties: { id: "MA001" } },
  { id: "MA002", type: "MergedAccount", label: "MergedAccount MA002", properties: { id: "MA002" } },
];

export const MOCK_EDGES: GraphEdge[] = [
  // A001 shares IP+LastName+Email with A002 → SAME_OWNER
  { id: "E1", source: "A001", target: "IP1", type: "HAS_IP", score: 0.2 },
  { id: "E2", source: "A002", target: "IP1", type: "HAS_IP", score: 0.2 },
  { id: "E3", source: "A001", target: "LN1", type: "HAS_LASTNAME", score: 0.3 },
  { id: "E4", source: "A002", target: "LN1", type: "HAS_LASTNAME", score: 0.3 },
  { id: "E5", source: "A001", target: "EM1", type: "HAS_EMAIL" },
  { id: "E6", source: "A002", target: "EM1", type: "HAS_EMAIL" },
  { id: "E_same1", source: "A001", target: "A002", type: "SAME_OWNER", score: 0.8 },
  // A003 shares device + phone with A004
  { id: "E7", source: "A003", target: "DV2", type: "HAS_DEVICE" },
  { id: "E8", source: "A004", target: "DV2", type: "HAS_DEVICE" },
  { id: "E9", source: "A003", target: "PH1", type: "HAS_PHONE" },
  { id: "E10", source: "A004", target: "PH1", type: "HAS_PHONE" },
  { id: "E_same2", source: "A003", target: "A004", type: "SAME_OWNER", score: 0.65 },
  // A005 — unique
  { id: "E11", source: "A005", target: "DV3", type: "HAS_DEVICE" },
  { id: "E12", source: "A005", target: "IP2", type: "HAS_IP" },
  { id: "E13", source: "A005", target: "AD2", type: "HAS_ADDRESS" },
  // A006 shares IP+LastName with A001
  { id: "E14", source: "A006", target: "IP1", type: "HAS_IP" },
  { id: "E15", source: "A006", target: "LN1", type: "HAS_LASTNAME" },
  { id: "E_same3", source: "A001", target: "A006", type: "SAME_OWNER", score: 0.6 },
  // VideoPlay connections
  { id: "E16", source: "A001", target: "VP1", type: "PLAYS_VIDEO" },
  { id: "E17", source: "VP1", target: "V001", type: "VIDEO_PLAYED" },
  { id: "E18", source: "A003", target: "VP2", type: "PLAYS_VIDEO" },
  { id: "E19", source: "VP2", target: "V002", type: "VIDEO_PLAYED" },
  { id: "E20", source: "A005", target: "VP3", type: "PLAYS_VIDEO" },
  { id: "E21", source: "VP3", target: "V001", type: "VIDEO_PLAYED" },
  // MERGED_INTO (entity resolution result)
  { id: "E22", source: "A001", target: "MA001", type: "MERGED_INTO" },
  { id: "E23", source: "A002", target: "MA001", type: "MERGED_INTO" },
  { id: "E24", source: "A006", target: "MA001", type: "MERGED_INTO" },
  { id: "E25", source: "A003", target: "MA002", type: "MERGED_INTO" },
  { id: "E26", source: "A004", target: "MA002", type: "MERGED_INTO" },
];

export const LOAD_STATS = {
  Account: { added: 6, loaded: 6, failed: 0 },
  IP: { added: 3, loaded: 3, failed: 0 },
  Email: { added: 2, loaded: 2, failed: 0 },
  LastName: { added: 2, loaded: 2, failed: 0 },
  Phone: { added: 2, loaded: 2, failed: 0 },
  Address: { added: 2, loaded: 2, failed: 0 },
  Device: { added: 3, loaded: 3, failed: 0 },
  VideoPlay: { added: 3, loaded: 3, failed: 0 },
  Video: { added: 2, loaded: 2, failed: 0 },
  MergedAccount: { added: 2, loaded: 2, failed: 0 },
};
