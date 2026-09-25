import { Router, type IRouter } from "express";
import healthRouter from "./health";
import roadContextRouter from "./road-context";

const router: IRouter = Router();

router.use(healthRouter);
router.use(roadContextRouter);

export default router;
