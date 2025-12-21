"use client";

import { useState, useEffect } from "react";
import { addComment, getComments, Comment } from "@/lib/api";
import { toast } from "sonner";
import { Send } from "lucide-react";

interface CommentSectionProps {
  newsletterId: string;
}

export default function CommentSection({ newsletterId }: CommentSectionProps) {
  const [formData, setFormData] = useState({
    author: "",
    email: "",
    content: "",
  });
  const [isLoading, setIsLoading] = useState(false);
  const [comments, setComments] = useState<Comment[]>([]);
  const [isLoadingComments, setIsLoadingComments] = useState(true);

  useEffect(() => {
    async function loadComments() {
      try {
        setIsLoadingComments(true);
        const data = await getComments(newsletterId);
        setComments(data);
      } catch (error) {
        console.error("Error loading comments:", error);
      } finally {
        setIsLoadingComments(false);
      }
    }
    loadComments();
  }, [newsletterId]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.author.trim() || !formData.email.trim() || !formData.content.trim()) {
      toast.error("Veuillez remplir tous les champs");
      return;
    }

    setIsLoading(true);
    try {
      const success = await addComment(newsletterId, formData);
      if (success) {
        toast.success("Commentaire publié avec succès!");
        setFormData({ author: "", email: "", content: "" });
        // Reload comments
        const data = await getComments(newsletterId);
        setComments(data);
      } else {
        toast.error("Erreur lors de la publication du commentaire");
      }
    } catch (error) {
      toast.error("Erreur de connexion");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section className="mt-12">
      <h3 className="text-2xl font-bold text-dark-text mb-8">Commentaires</h3>

      {/* Existing Comments */}
      {isLoadingComments ? (
        <div className="mb-8 text-dark-text-secondary">Chargement des commentaires...</div>
      ) : comments.length > 0 ? (
        <div className="mb-8 space-y-4">
          {comments.map((comment) => (
            <div
              key={comment._id}
              className="bg-dark-bg-secondary border border-white/10 rounded-lg p-4"
            >
              <div className="flex items-start justify-between mb-2">
                <div>
                  <p className="font-semibold text-dark-text">{comment.author}</p>
                  <p className="text-xs text-dark-text-secondary">
                    {new Date(comment.created_at).toLocaleDateString("fr-FR", {
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </p>
                </div>
              </div>
              <p className="text-dark-text-secondary mt-2">{comment.content}</p>
            </div>
          ))}
        </div>
      ) : (
        <div className="mb-8 text-dark-text-secondary">
          Aucun commentaire pour le moment. Soyez le premier à commenter !
        </div>
      )}

      <h4 className="text-xl font-bold text-dark-text mb-6">Laisser un commentaire</h4>

      <form onSubmit={handleSubmit} className="space-y-6 max-w-2xl">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Author Name */}
          <div>
            <label
              htmlFor="author"
              className="block text-sm font-semibold text-dark-text mb-2"
            >
              Nom
            </label>
            <input
              type="text"
              id="author"
              name="author"
              value={formData.author}
              onChange={handleChange}
              className="w-full px-4 py-2 rounded-lg bg-dark-bg-secondary border border-white/10 text-dark-text placeholder-dark-text-secondary focus:border-accent-teal focus:outline-none transition-colors"
              placeholder="Votre nom"
              disabled={isLoading}
            />
          </div>

          {/* Email */}
          <div>
            <label
              htmlFor="email"
              className="block text-sm font-semibold text-dark-text mb-2"
            >
              Email
            </label>
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              className="w-full px-4 py-2 rounded-lg bg-dark-bg-secondary border border-white/10 text-dark-text placeholder-dark-text-secondary focus:border-accent-teal focus:outline-none transition-colors"
              placeholder="votre@email.com"
              disabled={isLoading}
            />
          </div>
        </div>

        {/* Comment Content */}
        <div>
          <label
            htmlFor="content"
            className="block text-sm font-semibold text-dark-text mb-2"
          >
            Commentaire
          </label>
          <textarea
            id="content"
            name="content"
            value={formData.content}
            onChange={handleChange}
            rows={5}
            className="w-full px-4 py-3 rounded-lg bg-dark-bg-secondary border border-white/10 text-dark-text placeholder-dark-text-secondary focus:border-accent-teal focus:outline-none transition-colors resize-none"
            placeholder="Votre commentaire..."
            disabled={isLoading}
          />
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={isLoading}
          className="inline-flex items-center gap-2 px-8 py-3 bg-accent-teal text-dark-bg font-semibold rounded-lg hover:bg-accent-teal-hover transition-colors disabled:opacity-50"
        >
          <Send size={18} />
          {isLoading ? "Publication..." : "Publier le commentaire"}
        </button>
      </form>
    </section>
  );
}
