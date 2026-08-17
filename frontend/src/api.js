import axios from "axios";

const client = axios.create({
  baseURL: "http://127.0.0.1:5000",
  timeout: 120000,
});

export default {
  async setWorkspace(project_path) {
    const res = await client.post("/workspace", { project_path });
    return res.data;
  },
  async sendCommand(command) {
    const res = await client.post("/command", { command });
    return res.data;
  },
  async getHistory(limit = 50) {
    const res = await client.get("/history", { params: { limit } });
    return res.data;
  },
  async getFiles() {
    const res = await client.get("/files");
    return res.data;
  },
  async getFile(path) {
    const res = await client.get("/file", { params: { path } });
    return res.data;
  },
  async pickWorkspace() {
    const res = await client.get("/pick_workspace");
    return res.data;
  },
  async approve(changeId) {
    const res = await client.post(`/approve/${changeId}`);
    return res.data;
  },
  async reject(changeId) {
    const res = await client.post(`/reject/${changeId}`);
    return res.data;
  },
};
