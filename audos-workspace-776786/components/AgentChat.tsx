/**
 * AgentChat — thin glue between the platform-managed runtime hook and the
 * per-space view component.
 *
 * THIS FILE IS PLATFORM-MANAGED AND FORCE-OVERWRITTEN ON EVERY RECOMPILE.
 * Do not edit it per-space. To restyle the agent element, edit
 * `components/AgentChatView.tsx` instead. To change runtime/logic
 * (streaming, history loading, tool-use parsing, attachments, etc.), edit
 * `components/useAgentChatRuntime.tsx` in the genesis-space template — those
 * changes propagate to every workspace on the next compile.
 */
import AgentChatView from './AgentChatView';
import {
  useAgentChatRuntime,
  type AgentChatRuntimeProps,
} from './useAgentChatRuntime';

export type AgentChatProps = AgentChatRuntimeProps;

export default function AgentChat(props: AgentChatProps) {
  const runtime = useAgentChatRuntime(props);
  return <AgentChatView runtime={runtime} />;
}
