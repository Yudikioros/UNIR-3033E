"use client";
import { useParams } from "next/navigation";
import { PlanWorkspace } from "../../../components/capture/plan-workspace";

export default function Page() {
  const { id } = useParams<{ id: string }>();
  return <PlanWorkspace key={id} id={id} />;
}
