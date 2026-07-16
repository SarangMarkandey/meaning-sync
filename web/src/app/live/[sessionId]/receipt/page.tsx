import { ClarityReceiptView } from "@/components/clarity-receipt-view";

export default async function LiveReceiptPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;
  return <ClarityReceiptView sessionId={sessionId} />;
}
