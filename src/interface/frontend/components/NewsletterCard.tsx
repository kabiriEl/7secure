"use client";

import Link from "next/link";
import Image from "next/image";
import { Newsletter } from "@/lib/api";
import { formatDate, truncateText } from "@/lib/utils";
import { ArrowRight, Calendar, Clock } from "lucide-react";

interface NewsletterCardProps {
  newsletter: Newsletter;
  isSelected?: boolean;
}

export default function NewsletterCard({ newsletter, isSelected }: NewsletterCardProps) {
  return (
    <Link href={`/newsletter/${newsletter._id}`}>
      <article
        className={`group p-6 rounded-lg transition-all duration-300 cursor-pointer ${
          isSelected
            ? "bg-accent-teal text-dark-bg"
            : "bg-dark-bg-secondary hover:bg-dark-bg border border-white/10 hover:border-accent-teal"
        }`}
      >
        {/* Image */}
        {newsletter.image && (
          <div className="relative w-full h-48 mb-4 rounded-lg overflow-hidden bg-dark-bg">
            <Image
              src={newsletter.image}
              alt={newsletter.title}
              fill
              className="object-cover group-hover:scale-105 transition-transform duration-300"
            />
          </div>
        )}

        {/* Tags */}
        {newsletter.tags && newsletter.tags.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-3">
            {newsletter.tags.slice(0, 2).map((tag) => (
              <span
                key={tag}
                className={`text-xs font-semibold px-3 py-1 rounded-full ${
                  isSelected
                    ? "bg-dark-bg text-accent-teal"
                    : "bg-accent-teal text-dark-bg"
                }`}
              >
                {tag}
              </span>
            ))}
          </div>
        )}

        {/* Title */}
        <h2
          className={`text-xl font-bold mb-2 line-clamp-2 group-hover:text-accent-teal transition-colors ${
            isSelected ? "text-dark-bg" : ""
          }`}
        >
          {newsletter.title}
        </h2>

        {/* Excerpt */}
        <p
          className={`mb-4 line-clamp-2 text-sm ${
            isSelected ? "text-dark-bg/80" : "text-dark-text-secondary"
          }`}
        >
          {truncateText(newsletter.excerpt, 150)}
        </p>

        {/* Meta */}
        <div
          className={`flex items-center gap-4 text-xs mb-4 ${
            isSelected ? "text-dark-bg/70" : "text-dark-text-secondary"
          }`}
        >
          <div className="flex items-center gap-1">
            <Calendar size={14} />
            <time>{formatDate(newsletter.date)}</time>
          </div>
          {newsletter.readTime && (
            <div className="flex items-center gap-1">
              <Clock size={14} />
              <span>{newsletter.readTime} min</span>
            </div>
          )}
        </div>

        {/* Author */}
        <div className="flex items-center gap-2">
          {newsletter.author.avatar && (
            <Image
              src={newsletter.author.avatar}
              alt={newsletter.author.name}
              width={32}
              height={32}
              className="w-8 h-8 rounded-full object-cover"
            />
          )}
          <span
            className={`text-sm font-semibold ${
              isSelected ? "text-dark-bg" : "text-dark-text"
            }`}
          >
            {newsletter.author.name}
          </span>
        </div>

        {/* Read More */}
        <div
          className={`flex items-center gap-2 mt-4 font-semibold opacity-0 group-hover:opacity-100 transition-opacity ${
            isSelected ? "text-dark-bg" : "text-accent-teal"
          }`}
        >
          Lire la suite
          <ArrowRight size={18} />
        </div>
      </article>
    </Link>
  );
}
