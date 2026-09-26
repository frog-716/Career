export type WorkspaceRouteSnapshot = {
  page: string;
  projectId: string;
  employmentId: string;
  hash: string;
};

export type MutationRefreshStatus = "refreshed" | "refresh_failed" | "route_changed";

export type MutationRefreshPorts<T> = {
  captureRoute: () => WorkspaceRouteSnapshot;
  reload: () => Promise<void>;
  restoreRoute: (route: WorkspaceRouteSnapshot) => void;
  render: () => void;
  afterSave?: (value: T, context: { routeChangedDuringMutation: boolean }) => void;
  onRefreshError?: (error: unknown) => void;
};

export async function mutateAndRefreshWorkspace<T>(
  mutate: () => Promise<T>,
  ports: MutationRefreshPorts<T>,
): Promise<{ value: T; status: MutationRefreshStatus }> {
  const routeBeforeMutation = ports.captureRoute();
  const value = await mutate();
  const routeChangedDuringMutation = !sameRoute(routeBeforeMutation, ports.captureRoute());
  ports.afterSave?.(value, { routeChangedDuringMutation });
  const route = ports.captureRoute();

  try {
    await ports.reload();
  } catch (error) {
    if (sameRoute(route, ports.captureRoute())) {
      ports.restoreRoute(route);
      ports.render();
      ports.onRefreshError?.(error);
    }
    return { value, status: "refresh_failed" };
  }

  if (!sameRoute(route, ports.captureRoute())) {
    return { value, status: "route_changed" };
  }
  ports.restoreRoute(route);
  ports.render();
  return { value, status: "refreshed" };
}

function sameRoute(left: WorkspaceRouteSnapshot, right: WorkspaceRouteSnapshot): boolean {
  return left.page === right.page
    && left.projectId === right.projectId
    && left.employmentId === right.employmentId
    && left.hash === right.hash;
}
