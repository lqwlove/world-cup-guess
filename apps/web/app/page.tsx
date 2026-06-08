import { HomeHero } from "@/components/home/HomeHero";
import { AgentShowcase } from "@/components/home/AgentShowcase";
import { ScheduleSection } from "@/components/home/ScheduleSection";

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ date?: string; stage?: string; group?: string }>;
}) {
  const params = await searchParams;

  return (
    <>
      <div className="relative left-1/2 w-screen max-w-[100vw] -translate-x-1/2">
        <HomeHero />
      </div>
      <AgentShowcase />
      <ScheduleSection searchParams={params} />
    </>
  );
}
