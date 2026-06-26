import { useState } from "react";
import { Input } from '../components/antigravity/Input';
import { Button } from '../components/antigravity/Button';
import { supabase } from "../api/supabase";

const ASSIGNMENT_ID = "4a68496d-031a-4f82-9862-96122ad68323";

export default function TestRpc() {
  const [email, setEmail] = useState("test6@relopass.com");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<string>("");
  const [sessionEmail, setSessionEmail] = useState<string>("(checking...)");

  async function refreshSession() {
    const { data, error } = await supabase.auth.getUser();
    if (error || !data?.user) {
      setSessionEmail("NOT LOGGED IN");
    } else {
      setSessionEmail(data.user.email ?? data.user.id);
    }
  }

  async function signIn() {
    setStatus("Signing in...");
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) setStatus(`Sign-in error: ${error.message}`);
    else setStatus("Signed in ✅");
    await refreshSession();
  }

  async function signOut() {
    setStatus("Signing out...");
    await supabase.auth.signOut();
    setStatus("Signed out ✅");
    await refreshSession();
  }

  async function runRpc() {
    setStatus("Calling RPC...");
    const { data, error } = await supabase.rpc("transition_assignment", {
      p_assignment_id: ASSIGNMENT_ID,
      p_action: "EMPLOYEE_UNSUBMIT",
      p_note: null,
    });

    if (error) setStatus(`RPC error: ${error.code ?? ""} ${error.message}`);
    else setStatus(`RPC OK: ${JSON.stringify(data)}`);
  }

  // refresh session once on load
  useState(() => {
    void refreshSession();
  });

  return (
    <div style={{ padding: 24, fontFamily: "system-ui" }}>
      <h2>Test RPC</h2>
      <div style={{ marginBottom: 12 }}>
        <strong>Session:</strong> {sessionEmail}
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <Input unstyled
          style={{ padding: 8, width: 240 }}
          value={email}
          onChange={(v) => setEmail(v)}
          placeholder="email"
        />
        <Input unstyled
          style={{ padding: 8, width: 240 }}
          value={password}
          onChange={(v) => setPassword(v)}
          type="password"
          placeholder="password"
        />
        <Button unstyled onClick={signIn} style={{ padding: "8px 12px" }}>
          Sign in
        </Button>
        <Button unstyled onClick={signOut} style={{ padding: "8px 12px" }}>
          Sign out
        </Button>
      </div>

      <Button unstyled onClick={runRpc} style={{ padding: "10px 14px" }}>
        Run transition_assignment(EMPLOYEE_UNSUBMIT)
      </Button>

      <div style={{ marginTop: 16, whiteSpace: "pre-wrap" }}>{status}</div>
    </div>
  );
}