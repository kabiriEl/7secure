"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { Newsletter, fetchNewsletterById } from "@/lib/api";
import { formatFullDate, generateReadTime } from "@/lib/utils";
import { Calendar, Clock, ArrowLeft } from "lucide-react";
import CommentSection from "@/components/CommentSection";
import { Loader } from "lucide-react";

interface NewsletterPageProps {
  params: {
    id: string;
  };
}

export default function NewsletterPage({ params }: NewsletterPageProps) {
  const [newsletter, setNewsletter] = useState<Newsletter | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function loadNewsletter() {
      try {
        const data = await fetchNewsletterById(params.id);
        setNewsletter(data);
      } catch (error) {
        console.error("Error loading newsletter:", error);
      } finally {
        setIsLoading(false);
      }
    }

    loadNewsletter();
  }, [params.id]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader className="animate-spin text-accent-teal" size={40} />
      </div>
    );
  }

  if (!newsletter) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-dark-text mb-4">
            Newsletter non trouvée
          </h2>
          <Link
            href="/"
            className="inline-flex items-center gap-2 px-6 py-2 bg-accent-teal text-dark-bg font-semibold rounded-lg hover:bg-accent-teal-hover transition-colors"
          >
            <ArrowLeft size={18} />
            Retourner à l'accueil
          </Link>
        </div>
      </div>
    );
  }

  const readTime = newsletter.readTime || generateReadTime(newsletter.content);

  return (
    <article className="bg-dark-bg py-12">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Back Button */}
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-accent-teal hover:text-accent-teal-hover transition-colors mb-8"
        >
          <ArrowLeft size={18} />
          Retour
        </Link>

        {/* Header */}
        <header className="mb-12">
          {/* Tags */}
          {newsletter.tags && newsletter.tags.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-6">
              {newsletter.tags.map((tag) => (
                <span
                  key={tag}
                  className="inline-block px-3 py-1 text-xs font-semibold bg-accent-teal text-dark-bg rounded-full"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}

          {/* Title */}
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-dark-text mb-6 leading-tight">
            {newsletter.title}
          </h1>

          {/* Meta */}
          <div className="flex flex-col sm:flex-row gap-6 items-start sm:items-center border-b border-white/10 pb-8">
            {/* Author */}
            <div className="flex items-center gap-4">
              {newsletter.author.avatar && (
                <Image
                  src={newsletter.author.avatar}
                  alt={newsletter.author.name}
                  width={56}
                  height={56}
                  className="w-14 h-14 rounded-full object-cover"
                />
              )}
              <div>
                <p className="font-semibold text-dark-text">{newsletter.author.name}</p>
                <p className="text-dark-text-secondary text-sm">Auteur</p>
              </div>
            </div>

            {/* Date and Reading Time */}
            <div className="flex flex-wrap gap-6 sm:ml-auto">
              <div className="flex items-center gap-2 text-dark-text-secondary">
                <Calendar size={18} />
                <span>{formatFullDate(newsletter.date)}</span>
              </div>
              <div className="flex items-center gap-2 text-dark-text-secondary">
                <Clock size={18} />
                <span>{readTime} min de lecture</span>
              </div>
            </div>
          </div>
        </header>

        {/* Featured Image */}
        {newsletter.image && (
          <div className="relative w-full h-96 rounded-lg overflow-hidden mb-12">
            <Image
              src={newsletter.image}
              alt={newsletter.title}
              fill
              className="object-cover"
              priority
            />
          </div>
        )}

        {/* Content */}
        <div className="prose prose-invert max-w-none mb-16">
          {newsletter.html ? (
            <div
              className="text-dark-text-secondary leading-relaxed"
              dangerouslySetInnerHTML={{ __html: newsletter.html }}
            />
          ) : (
            <div
              className="text-dark-text-secondary leading-relaxed"
              dangerouslySetInnerHTML={{
                __html: newsletter.content
                  .replace(/\n\n/g, "</p><p>")
                  .replace(/^/, "<p>")
                  .replace(/$/, "</p>"),
              }}
            />
          )}
        </div>

        {/* Divider */}
        <hr className="border-white/10 my-12" />

        {/* Comments Section */}
        <CommentSection newsletterId={newsletter._id} />
      </div>
    </article>
  );
}
