import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Dna,
  Search,
  FileText,
  Image,
  FlaskConical,
  Atom,
  ArrowRight,
  Sparkles,
  Network,
  Shield,
} from 'lucide-react';

export default function HomePage() {
  const navigate = useNavigate();

  return (
    <div className="max-w-6xl mx-auto">
      {/* Hero Section */}
      <section className="text-center py-16">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary-500/10 text-primary-400 text-sm font-medium mb-6">
            <Sparkles size={16} />
            <span>Powered by Gemini 2.5 Flash + Qdrant</span>
          </div>

          <h1 className="text-5xl md:text-6xl font-bold mb-6">
            <span className="gradient-text">Discover Biological</span>
            <br />
            <span className="text-dark-100">Insights with AI</span>
          </h1>

          <p className="text-xl text-dark-400 max-w-2xl mx-auto mb-8">
            Multi-modal search across proteins, articles, images, experiments, and structures.
            Find related entities with intelligent cross-modal recommendations.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-4">
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => navigate('/search')}
              className="btn-primary flex items-center gap-2 px-8 py-4 text-lg"
            >
              <Search size={20} />
              Start Exploring
              <ArrowRight size={20} />
            </motion.button>
          </div>
        </motion.div>
      </section>

      {/* Features Grid */}
      <section className="py-16">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="text-center mb-12"
        >
          <h2 className="text-3xl font-bold text-dark-100 mb-4">Multi-Modal Search</h2>
          <p className="text-dark-400">Search across 5 different biological data types</p>
        </motion.div>

        <div className="grid md:grid-cols-5 gap-4">
          <FeatureCard
            icon={<Dna className="text-bio-protein" />}
            title="Proteins"
            description="Search by sequence or function"
            color="protein"
            delay={0.1}
          />
          <FeatureCard
            icon={<FileText className="text-bio-article" />}
            title="Articles"
            description="Literature & publications"
            color="article"
            delay={0.2}
          />
          <FeatureCard
            icon={<Image className="text-bio-image" />}
            title="Images"
            description="Pathways & gene profiles"
            color="image"
            delay={0.3}
          />
          <FeatureCard
            icon={<FlaskConical className="text-bio-experiment" />}
            title="Experiments"
            description="GEO datasets & results"
            color="experiment"
            delay={0.4}
          />
          <FeatureCard
            icon={<Atom className="text-bio-structure" />}
            title="Structures"
            description="PDB & AlphaFold"
            color="structure"
            delay={0.5}
          />
        </div>
      </section>

      {/* How It Works */}
      <section className="py-16">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="text-center mb-12"
        >
          <h2 className="text-3xl font-bold text-dark-100 mb-4">Intelligent Workflow</h2>
          <p className="text-dark-400">Three-layer LLM architecture for optimal results</p>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-6">
          <WorkflowCard
            step={1}
            title="Keyword Extraction"
            description="LLM extracts genes, diseases, and keywords from your query for hybrid search"
            icon={<Search />}
            delay={0.6}
          />
          <WorkflowCard
            step={2}
            title="Cross-Modal Search"
            description="Parallel search across all collections using generated queries"
            icon={<Network />}
            delay={0.7}
          />
          <WorkflowCard
            step={3}
            title="Design Assistant"
            description="Diverse candidates with justifications for research directions"
            icon={<Sparkles />}
            delay={0.8}
          />
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-16">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.9 }}
          className="card p-12 text-center"
        >
          <Shield className="w-16 h-16 text-primary-500 mx-auto mb-6" />
          <h2 className="text-3xl font-bold text-dark-100 mb-4">
            Scientific Traceability
          </h2>
          <p className="text-dark-400 max-w-xl mx-auto mb-8">
            Every recommendation comes with evidence links, confidence scores, and direct
            connections to primary data sources.
          </p>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => navigate('/search')}
            className="btn-primary"
          >
            Try Now
          </motion.button>
        </motion.div>
      </section>
    </div>
  );
}

interface FeatureCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  color: string;
  delay: number;
}

function FeatureCard({ icon, title, description, color, delay }: FeatureCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      whileHover={{ scale: 1.05, y: -5 }}
      className="card-hover p-6 text-center cursor-pointer"
    >
      <div className={`w-14 h-14 rounded-xl bg-bio-${color}/10 flex items-center justify-center mx-auto mb-4`}>
        {icon}
      </div>
      <h3 className="font-semibold text-dark-100 mb-2">{title}</h3>
      <p className="text-sm text-dark-400">{description}</p>
    </motion.div>
  );
}

interface WorkflowCardProps {
  step: number;
  title: string;
  description: string;
  icon: React.ReactNode;
  delay: number;
}

function WorkflowCard({ step, title, description, icon, delay }: WorkflowCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      className="card p-6 relative"
    >
      <div className="absolute -top-4 -left-4 w-10 h-10 rounded-full bg-gradient-to-br from-primary-500 to-purple-500 flex items-center justify-center text-white font-bold">
        {step}
      </div>
      <div className="pt-4">
        <div className="w-12 h-12 rounded-lg bg-dark-800 flex items-center justify-center text-primary-400 mb-4">
          {icon}
        </div>
        <h3 className="font-semibold text-dark-100 mb-2">{title}</h3>
        <p className="text-sm text-dark-400">{description}</p>
      </div>
    </motion.div>
  );
}
