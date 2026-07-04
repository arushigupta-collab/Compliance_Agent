import { redirect } from "next/navigation";

export default async function ProcessIndex({ params }: { params: Promise<{ sr: string; runId: string }> }) {
  const { sr, runId } = await params;
  // The process is presented per-stage; land on DVO.
  redirect(`/companies/${sr}/process/${runId}/dvo`);
}
