from sentence_transformers import SentenceTransformer, util
import torch

# Load model (multilingual)
device = "cuda" if torch.cuda.is_available() else "cpu"
model = SentenceTransformer("intfloat/multilingual-e5-base", device=device)

def filter_clips(clips, query, threshold=0.5):
    # 2. Embed Each Transcript
    for clip in clips:
        clip["embedding"] = model.encode(clip["transcript"], convert_to_tensor=True)

    # 3. Query Embedding
    query_embedding = model.encode(query, convert_to_tensor=True)

    # 4. Cosine Similarity & Filter
    results = []
    for clip in clips:
        sim_score = util.cos_sim(query_embedding, clip["embedding"]).item()
        if sim_score >= threshold:
            clip["similarity"] = sim_score
            results.append(clip)

    # 5. Sort by similarity (descending)
    results = sorted(results, key=lambda x: x["similarity"], reverse=True)

    # 6. Remove 'embedding' before returning
    for clip in results:
        clip.pop("embedding", None)

    print(results)
    return results


if __name__ == "__main__":
    clips = [
        {
        "viralScore": "9.2",
        "relatedTopic": "[\"feminism\",\"man-hating myth\",\"gender equality\",\"misconceptions\"]",
        "transcript": ". I was appointed six months ago. And the more I've spoken about feminism, the more I have realized that fighting for women's rights has too often become synonymous with man-hating. If there is one thing I know for certain, it is that this has to stop.",
        "videoUrl": "https://res.cloudinary.com/dbnf4vmma/video/upload/v1756114583/reels/ftkgfhryump8re3nvkci.mp4",
        "clipEditorUrl": "https://vizard.ai/editor?id=127646828&type=clip",
        "videoMsDuration": 38827,
        "videoId": 18661451,
        "title": "Why Feminism Is NOT About Man-Hating | Powerful Truth",
        "viralReason": "This clip opens with a strong challenge to a common misconception about feminism, creating immediate curiosity and emotional engagement, making it perfect for sparking conversation and shares."
        },
        {
        "viralScore": "9",
        "relatedTopic": "[\"personal story\",\"gender stereotypes\",\"sexualization\",\"peer pressure\"]",
        "transcript": "I started questioning gender-based assumptions a long time ago. When I was eight, I was confused with being called bossy because I wanted to direct the plays that we would put on for our parents. But the boys were not. When at 14, I started to be sexualized by certain elements of the media. When at 15, my girlfriends started dropping out of their beloved sports teams because they didn't want to appear muscly. When at 18, my male friends were unable to express their feelings.",
        "videoUrl": "https://res.cloudinary.com/dbnf4vmma/video/upload/v1756114614/reels/bppz38n4g1s2by9becnc.mp4",
        "clipEditorUrl": "https://vizard.ai/editor?id=127646827&type=clip",
        "videoMsDuration": 42482,
        "videoId": 18661449,
        "title": "My Journey Facing Gender Stereotypes & Society’s Pressure",
        "viralReason": "This clip contains a compelling personal narrative with emotional vulnerability and relatable conflict about early experiences with gender bias and societal pressures, engaging viewers on a deep human level."
        }
    ]
    query = "talks about feminism and misconceptions"
    filter_clips(clips, query)
