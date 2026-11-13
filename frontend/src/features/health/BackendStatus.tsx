import { useQuery } from "@tanstack/react-query";

import { getHealth } from "../../lib/api";

const healthQueryKey = ["health"] as const;

export function BackendStatus() {
  const { isPending, isError } = useQuery({
    queryKey: healthQueryKey,
    queryFn: getHealth,
    refetchInterval: 30_000,
  });

  const [dot, label] = isPending
    ? ["bg-slate-400", "Checking backend…"]
    : isError
      ? ["bg-red-500", "Backend offline"]
      : ["bg-emerald-500", "Backend connected"];

  return (
    <span
      role="status"
      className="inline-flex items-center gap-2 text-sm text-slate-600"
    >
      <span aria-hidden="true" className={`size-2 rounded-full ${dot}`} />
      {label}
    </span>
  );
}
