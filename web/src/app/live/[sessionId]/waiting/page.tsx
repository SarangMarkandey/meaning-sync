import { LiveWaitingRoom } from "@/components/live-waiting-room";

export default async function LiveWaitingPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;
  return <LiveWaitingRoom sessionId={sessionId} />;
}
