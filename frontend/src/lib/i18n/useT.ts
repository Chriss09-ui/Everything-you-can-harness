/** useT — 翻译钩子。
 *
 * 从 profileStore.language 读当前语言，返回 t(key)。
 * 切换语言时所有用了 useT 的组件自动重渲染（zustand 订阅）。
 */
import { useProfileStore } from "@/stores/profileStore";
import { dict, type Key } from "./dict";

export function useT(): (key: Key) => string {
  const lang = useProfileStore((s) => s.profile.language);
  return (key: Key) => dict[lang][key];
}
