import { LiveSessionExperience } from "@/components/live-session-experience";

export default async function LiveSessionPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;
  return <LiveSessionExperience sessionId={sessionId} />;
}
