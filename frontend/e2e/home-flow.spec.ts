import { test, expect } from "@playwright/test";

test("submits trip form and opens generated itinerary", async ({ page }) => {
  await page.route("**/api/trips/generate", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "trip-1",
        title: "Shanghai weekend",
        input: {
          city: "Shanghai",
          date: "2026-05-16",
          days: 1,
          budget: 500,
          interests: ["food"],
          companions: "friends",
        },
        region: "domestic",
        items: [],
        total_budget: 500,
        weather_summary: { summary: "sunny" },
        transportation: { summary: "No departure city provided", trains: [] },
        notes: [],
        created_at: "2026-05-09T00:00:00Z",
      }),
    });
  });
  await page.goto("/");
  await page.getByLabel("Date").fill("2026-05-16");
  await page.getByRole("button", { name: "Generate itinerary" }).click();
  await expect(page).toHaveURL(/\/itinerary\/trip-1/);
});
