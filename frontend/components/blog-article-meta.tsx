import { blogDate } from "@/lib/blog-posts";

export function BlogArticleMeta({ post }: {
  post: { publishedAt: string; updatedAt: string; category: string };
}) {
  return (
    <p className="blog-article-meta">
      Published <time dateTime={post.publishedAt}>{blogDate(post.publishedAt)}</time>
      {" · "}Updated <time dateTime={post.updatedAt}>{blogDate(post.updatedAt)}</time>
      {" · "}{post.category}
    </p>
  );
}
