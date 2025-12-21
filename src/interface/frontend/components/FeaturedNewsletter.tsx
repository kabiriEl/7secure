"use client";

import Image from "next/image";
import Link from "next/link";
import { Newsletter } from "@/lib/api";
import { formatFullDate, generateReadTime } from "@/lib/utils";
import { Calendar, Clock, ArrowRight } from "lucide-react";

interface FeaturedNewsletterProps {
  newsletter: Newsletter;
}

export default function FeaturedNewsletter({ newsletter }: FeaturedNewsletterProps) {
  const readTime = newsletter.readTime || generateReadTime(newsletter.content);

  return (
    <section className="relative bg-gradient-to-b from-dark-bg-secondary to-dark-bg py-20 border-b border-white/10">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-12 items-center">
          {/* Content */}
          <div>
            {/* Badges */}
            {newsletter.tags && newsletter.tags.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-6">
                {newsletter.tags.slice(0, 3).map((tag) => (
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

            {/* Excerpt */}
            <p className="text-lg text-dark-text-secondary mb-8">{newsletter.excerpt}</p>

            {/* Meta */}
            <div className="flex flex-col sm:flex-row gap-6 mb-8 text-sm">
              {/* Author */}
              <div className="flex items-center gap-3">
                {newsletter.author.avatar && (
                  <Image
                    src={newsletter.author.avatar}
                    alt={newsletter.author.name}
                    width={48}
                    height={48}
                    className="w-12 h-12 rounded-full object-cover"
                  />
                )}
                <div>
                  <p className="font-semibold text-dark-text">{newsletter.author.name}</p>
                  <p className="text-dark-text-secondary text-xs">Auteur</p>
                </div>
              </div>

              {/* Date and Reading Time */}
              <div className="flex flex-wrap gap-4 sm:border-l border-white/10 sm:pl-4">
                <div className="flex items-center gap-2 text-dark-text-secondary">
                  <Calendar size={16} />
                  <span>{formatFullDate(newsletter.date)}</span>
                </div>
                <div className="flex items-center gap-2 text-dark-text-secondary">
                  <Clock size={16} />
                  <span>{readTime} min de lecture</span>
                </div>
              </div>
            </div>

            {/* CTA Button */}
            <Link
              href={`/newsletter/${newsletter._id}`}
              className="inline-flex items-center gap-2 px-8 py-3 bg-accent-teal text-dark-bg font-semibold rounded-lg hover:bg-accent-teal-hover transition-colors"
            >
              Lire l'article complet
              <ArrowRight size={20} />
            </Link>
          </div>

          {/* Image */}
          {newsletter.image && (
            <div className="relative h-64 sm:h-80 lg:h-96 rounded-lg overflow-hidden">
              <Image
                src={newsletter.image}
                alt={newsletter.title}
                fill
                className="object-cover"
                priority
              />
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
