import { post, get } from './request';
import type { PredictionRequest, PredictionResult } from '@/types/prediction';

export function createPrediction(data: PredictionRequest) {
  return post<PredictionResult>('/predictions', data);
}

export function getPrediction(id: number) {
  return get<PredictionResult>(`/predictions/${id}`);
}
