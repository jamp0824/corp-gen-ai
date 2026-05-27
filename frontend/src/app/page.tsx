import { redirect } from "next/navigation";

/** 루트("/")는 Step 2로 바로 리다이렉트 */
export default function RootPage() {
  redirect("/step2");
}
